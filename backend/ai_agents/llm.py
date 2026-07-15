from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar

import httpx

from services.llm_privacy import pseudonymize_prompt

logger = logging.getLogger(__name__)

# AGENT-11: retry breve su timeout/5xx/output malformato, poi fallback.
LLM_RETRY_MAX = 2
LLM_RETRY_BACKOFF_SECONDS: tuple[float, ...] = (0.5, 1.0)

_T = TypeVar("_T")


@dataclass
class AgentLlmResult:
    subject: str
    body: str
    provider: str
    model: Optional[str] = None
    raw_text: Optional[str] = None
    prompt_version: Optional[str] = None


def _is_retryable_llm_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    # Output malformato (JSON invalido, schema non rispettato): vale la pena ritentare.
    if isinstance(exc, ValueError):
        return True
    return False


def _log_llm_call(
    *,
    agent: str,
    provider: str,
    model: Optional[str],
    prompt_version: Optional[str],
    attempt: int,
    outcome: str,
    duration_ms: int,
    error_class: Optional[str] = None,
) -> None:
    """Log strutturato per chiamata LLM. MAI contenuti di prompt o documenti."""
    logger.info(
        "agent_llm_call %s",
        json.dumps(
            {
                "agent": agent,
                "provider": provider,
                "model": model,
                "prompt_version": prompt_version,
                "attempt": attempt,
                "outcome": outcome,
                "duration_ms": duration_ms,
                "error_class": error_class,
            },
            ensure_ascii=True,
        ),
    )


def call_llm_with_retry(
    call: Callable[[], _T],
    *,
    agent: str,
    prompt_version: Optional[str] = None,
) -> _T:
    """Esegue una chiamata LLM con retry (max LLM_RETRY_MAX) e backoff breve.

    Ritenta su timeout, errori di trasporto, 5xx e output malformato
    (ValueError). Esauriti i retry rilancia l'ultima eccezione: la gestione
    del fallback resta al chiamante (mail: deterministico; documenti:
    manual_review).
    """
    config = get_agent_llm_config()
    attempts = LLM_RETRY_MAX + 1
    for attempt in range(1, attempts + 1):
        started = time.monotonic()
        try:
            result = call()
        except Exception as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            retryable = _is_retryable_llm_error(exc)
            _log_llm_call(
                agent=agent,
                provider=config.provider,
                model=config.model,
                prompt_version=prompt_version,
                attempt=attempt,
                outcome="retry" if (retryable and attempt < attempts) else "failed",
                duration_ms=duration_ms,
                error_class=exc.__class__.__name__,
            )
            if not retryable or attempt >= attempts:
                raise
            backoff = LLM_RETRY_BACKOFF_SECONDS[min(attempt - 1, len(LLM_RETRY_BACKOFF_SECONDS) - 1)]
            time.sleep(backoff)
            continue
        duration_ms = int((time.monotonic() - started) * 1000)
        _log_llm_call(
            agent=agent,
            provider=config.provider,
            model=config.model,
            prompt_version=prompt_version,
            attempt=attempt,
            outcome="ok",
            duration_ms=duration_ms,
        )
        return result
    raise RuntimeError("unreachable")  # pragma: no cover


@dataclass
class AgentLlmConfig:
    provider: str
    model: Optional[str]
    timeout_seconds: float
    ollama_base_url: str
    openclaw_base_url: str
    openclaw_api_key: Optional[str]
    openclaw_path: str

    @property
    def enabled(self) -> bool:
        return self.provider in {"ollama", "openclaw"}


@dataclass
class AgentLlmHealthResult:
    provider: str
    enabled: bool
    model: Optional[str]
    base_url: Optional[str]
    reachable: bool
    status_code: Optional[int]
    detail: str


def get_agent_llm_config() -> AgentLlmConfig:
    provider = (os.getenv("AI_AGENT_LLM_PROVIDER", "none") or "none").strip().lower()
    return AgentLlmConfig(
        provider=provider,
        model=os.getenv("AI_AGENT_LLM_MODEL"),
        timeout_seconds=float(os.getenv("AI_AGENT_LLM_TIMEOUT_SECONDS", "25")),
        ollama_base_url=(os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434") or "").rstrip("/"),
        openclaw_base_url=(os.getenv("OPENCLAW_BASE_URL", "") or "").rstrip("/"),
        openclaw_api_key=os.getenv("OPENCLAW_API_KEY"),
        openclaw_path=os.getenv("OPENCLAW_CHAT_PATH", "/v1/chat/completions"),
    )


def is_agent_llm_enabled() -> bool:
    return get_agent_llm_config().enabled


def probe_agent_llm_health() -> AgentLlmHealthResult:
    config = get_agent_llm_config()

    if not config.enabled:
        return AgentLlmHealthResult(
            provider=config.provider,
            enabled=False,
            model=config.model,
            base_url=None,
            reachable=False,
            status_code=None,
            detail="Provider LLM disabilitato",
        )

    if config.provider == "ollama":
        return _probe_ollama_health(config)
    if config.provider == "openclaw":
        return _probe_openclaw_health(config)

    return AgentLlmHealthResult(
        provider=config.provider,
        enabled=False,
        model=config.model,
        base_url=None,
        reachable=False,
        status_code=None,
        detail="Provider LLM non supportato",
    )


def generate_mail_recovery_copy(
    *,
    collaborator_name: str,
    collaborator_email: Optional[str],
    context_label: str,
    requested_tone: str,
    fallback_subject: str,
    fallback_body: str,
    missing_fields: Optional[list[str]] = None,
    days_to_expiry: Optional[int] = None,
) -> Optional[AgentLlmResult]:
    config = get_agent_llm_config()
    if not config.enabled:
        return None

    prompt_payload = {
        "collaborator_name": collaborator_name,
        "collaborator_email": collaborator_email,
        "context_label": context_label,
        "requested_tone": requested_tone,
        "missing_fields": missing_fields or [],
        "days_to_expiry": days_to_expiry,
        "fallback_subject": fallback_subject,
        "fallback_body": fallback_body,
    }

    from .prompts import mail_recovery_v1

    context_instructions = _build_mail_context_instructions(
        context_label=context_label,
        missing_fields=missing_fields or [],
        days_to_expiry=days_to_expiry,
    )
    system_prompt = mail_recovery_v1.SYSTEM_PROMPT
    user_prompt = mail_recovery_v1.build_user_prompt(
        context_instructions=context_instructions,
        prompt_payload_json=json.dumps(prompt_payload, ensure_ascii=True, default=str),
    )

    def _invoke() -> AgentLlmResult:
        if config.provider == "ollama":
            return _call_ollama(config, system_prompt=system_prompt, user_prompt=user_prompt)
        if config.provider == "openclaw":
            return _call_openclaw(config, system_prompt=system_prompt, user_prompt=user_prompt)
        raise RuntimeError(f"Provider LLM non supportato: {config.provider}")

    try:
        result = call_llm_with_retry(
            _invoke,
            agent="mail_recovery",
            prompt_version=mail_recovery_v1.PROMPT_VERSION,
        )
        result.prompt_version = mail_recovery_v1.PROMPT_VERSION
        if _is_mail_copy_acceptable(
            context_label=context_label,
            body=result.body,
            missing_fields=missing_fields or [],
        ):
            return result
        logger.warning("LLM agent fallback attivato su provider %s: output non conforme ai controlli minimi", config.provider)
    except Exception as exc:
        logger.warning("LLM agent fallback attivato su provider %s: %s", config.provider, exc.__class__.__name__)
    return None




def call_ollama_json(
    *,
    system_prompt: str,
    user_prompt: str,
) -> dict:
    """
    Chiama Ollama e ritorna un dizionario JSON generico.
    Non impone vincoli su subject/body — usabile per DocumentProcessor
    e qualsiasi agente che non genera email.
    """
    config = get_agent_llm_config()
    if not config.enabled:
        raise RuntimeError("Provider LLM non abilitato")

    if config.provider == "ollama":
        if not config.model:
            raise ValueError("AI_AGENT_LLM_MODEL obbligatorio per provider ollama")

        payload = {
            "model": config.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {
                "temperature": 0.1,
            },
        }

        with httpx.Client(timeout=config.timeout_seconds) as client:
            response = client.post(f"{config.ollama_base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()

        raw_text = ((data.get("message") or {}).get("content") or "").strip()

    elif config.provider == "openclaw":
        if not config.openclaw_base_url:
            raise ValueError("OPENCLAW_BASE_URL obbligatorio per provider openclaw")
        if not config.model:
            raise ValueError("AI_AGENT_LLM_MODEL obbligatorio per provider openclaw")

        headers = {"Content-Type": "application/json"}
        if config.openclaw_api_key:
            headers["Authorization"] = f"Bearer {config.openclaw_api_key}"

        private_prompt = pseudonymize_prompt(user_prompt)
        payload = {
            "model": config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": private_prompt.text},
            ],
            "temperature": 0.1,
        }

        with httpx.Client(timeout=config.timeout_seconds) as client:
            response = client.post(
                f"{config.openclaw_base_url}{config.openclaw_path}",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        choices = data.get("choices") or []
        raw_text = ""
        if choices:
            raw_text = (((choices[0] or {}).get("message") or {}).get("content") or "").strip()
        raw_text = private_prompt.restore(raw_text)
    else:
        raise RuntimeError(f"Provider LLM non supportato: {config.provider}")

    if not raw_text:
        raise ValueError("Risposta LLM vuota")

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Risposta LLM non in formato JSON")
        parsed = json.loads(raw_text[start:end + 1])

    if not isinstance(parsed, dict):
        raise ValueError("Risposta LLM JSON non e un oggetto")

    return parsed

def _call_ollama(config: AgentLlmConfig, *, system_prompt: str, user_prompt: str) -> AgentLlmResult:
    if not config.model:
        raise ValueError("AI_AGENT_LLM_MODEL obbligatorio per provider ollama")

    payload = {
        "model": config.model,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "options": {
            "temperature": 0.3,
        },
    }

    with httpx.Client(timeout=config.timeout_seconds) as client:
        response = client.post(f"{config.ollama_base_url}/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()

    raw_text = ((data.get("message") or {}).get("content") or "").strip()
    parsed = _parse_json_object(raw_text)
    copy = _validate_mail_copy(parsed)
    subject, body = _normalize_mail_copy(copy.subject, copy.body)
    return AgentLlmResult(
        subject=subject,
        body=body,
        provider="ollama",
        model=config.model,
        raw_text=raw_text,
    )


def _call_openclaw(config: AgentLlmConfig, *, system_prompt: str, user_prompt: str) -> AgentLlmResult:
    if not config.openclaw_base_url:
        raise ValueError("OPENCLAW_BASE_URL obbligatorio per provider openclaw")
    if not config.model:
        raise ValueError("AI_AGENT_LLM_MODEL obbligatorio per provider openclaw")

    headers = {"Content-Type": "application/json"}
    if config.openclaw_api_key:
        headers["Authorization"] = f"Bearer {config.openclaw_api_key}"

    private_prompt = pseudonymize_prompt(user_prompt)
    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": private_prompt.text},
        ],
        "temperature": 0.3,
    }

    with httpx.Client(timeout=config.timeout_seconds) as client:
        response = client.post(
            f"{config.openclaw_base_url}{config.openclaw_path}",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

    choices = data.get("choices") or []
    raw_text = ""
    if choices:
        raw_text = (((choices[0] or {}).get("message") or {}).get("content") or "").strip()
    raw_text = private_prompt.restore(raw_text)
    parsed = _parse_json_object(raw_text)
    copy = _validate_mail_copy(parsed)
    subject, body = _normalize_mail_copy(copy.subject, copy.body)
    return AgentLlmResult(
        subject=subject,
        body=body,
        provider="openclaw",
        model=config.model,
        raw_text=raw_text,
    )


def _probe_ollama_health(config: AgentLlmConfig) -> AgentLlmHealthResult:
    try:
        with httpx.Client(timeout=min(config.timeout_seconds, 5.0)) as client:
            response = client.get(f"{config.ollama_base_url}/api/tags")
        if response.is_success:
            data = response.json()
            models = [item.get("name") for item in data.get("models", []) if item.get("name")]
            detail = "Ollama raggiungibile"
            if config.model and config.model not in models:
                detail = f"Ollama raggiungibile, ma modello {config.model} non presente"
            return AgentLlmHealthResult(
                provider="ollama",
                enabled=True,
                model=config.model,
                base_url=config.ollama_base_url,
                reachable=True,
                status_code=response.status_code,
                detail=detail,
            )
        return AgentLlmHealthResult(
            provider="ollama",
            enabled=True,
            model=config.model,
            base_url=config.ollama_base_url,
            reachable=False,
            status_code=response.status_code,
            detail=f"Ollama ha risposto con status {response.status_code}",
        )
    except Exception as exc:
        return AgentLlmHealthResult(
            provider="ollama",
            enabled=True,
            model=config.model,
            base_url=config.ollama_base_url,
            reachable=False,
            status_code=None,
            detail=f"Connessione Ollama fallita: {exc}",
        )


def _probe_openclaw_health(config: AgentLlmConfig) -> AgentLlmHealthResult:
    try:
        with httpx.Client(timeout=min(config.timeout_seconds, 5.0)) as client:
            response = client.get(config.openclaw_base_url or "http://127.0.0.1:18789")
        reachable = response.status_code < 500
        detail = "Gateway OpenClaw raggiungibile"
        if not config.openclaw_api_key:
            detail += ", token non configurato"
        if not config.model:
            detail += ", model non configurato"
        detail += f", chat path previsto: {config.openclaw_path}"
        return AgentLlmHealthResult(
            provider="openclaw",
            enabled=True,
            model=config.model,
            base_url=config.openclaw_base_url or "http://127.0.0.1:18789",
            reachable=reachable,
            status_code=response.status_code,
            detail=detail,
        )
    except Exception as exc:
        return AgentLlmHealthResult(
            provider="openclaw",
            enabled=True,
            model=config.model,
            base_url=config.openclaw_base_url or "http://127.0.0.1:18789",
            reachable=False,
            status_code=None,
            detail=f"Connessione OpenClaw fallita: {exc}",
        )


def _parse_json_object(raw_text: str) -> dict[str, Any]:
    if not raw_text:
        raise ValueError("Risposta LLM vuota")

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Risposta LLM non in formato JSON")
        parsed = json.loads(raw_text[start:end + 1])

    if not isinstance(parsed, dict):
        raise ValueError("Risposta LLM JSON non oggetto")
    return parsed


def _validate_mail_copy(parsed: dict):
    """Valida l'output mail con MailCopySchema; malformato -> ValueError (retry)."""
    from pydantic import ValidationError

    from .llm_schemas import MailCopySchema

    try:
        return MailCopySchema.model_validate(parsed)
    except ValidationError as exc:
        raise ValueError(
            f"Output LLM non conforme a MailCopySchema ({exc.error_count()} errori)"
        ) from exc


def _build_mail_context_instructions(
    *,
    context_label: str,
    missing_fields: list[str],
    days_to_expiry: Optional[int],
) -> str:
    if context_label == "missing_collaborator_data":
        return (
            "Si tratta di recupero dati anagrafici/professionali mancanti. "
            f"I campi mancanti da citare sono: {', '.join(missing_fields) if missing_fields else 'non specificati'}. "
            "Non introdurre richieste aggiuntive."
        )
    if context_label == "identity_document_followup":
        if days_to_expiry is None:
            expiry_text = "documento mancante oppure data di scadenza non registrata"
        elif days_to_expiry < 0:
            expiry_text = f"documento scaduto da {abs(days_to_expiry)} giorni"
        else:
            expiry_text = f"documento in scadenza tra {days_to_expiry} giorni"
        return (
            "Si tratta di aggiornamento documento di identita. "
            f"Situazione da menzionare: {expiry_text}. "
            "Chiedi solo l'invio del documento aggiornato e, se serve, della data di scadenza."
        )
    return "Mantieni il testo aderente al contesto fornito."


def _normalize_mail_copy(subject: Any, body: Any) -> tuple[str, str]:
    clean_subject = " ".join(str(subject or "").strip().split())
    clean_body = str(body or "").strip().replace("\r\n", "\n")
    while "\n\n\n" in clean_body:
        clean_body = clean_body.replace("\n\n\n", "\n\n")

    replacements = {
        "\nCiao, \nIl nostro team": "\n\nGrazie per la collaborazione.",
        "\nCiao,\nIl nostro team": "\n\nGrazie per la collaborazione.",
        "\nCordiali saluti,\nIl nostro team": "\n\nGrazie per la collaborazione.",
    }
    for source, target in replacements.items():
        clean_body = clean_body.replace(source, target)

    if not clean_subject or not clean_body:
        raise ValueError("Risposta LLM normalizzata vuota")
    return clean_subject, clean_body


def _is_mail_copy_acceptable(*, context_label: str, body: str, missing_fields: list[str]) -> bool:
    normalized_body = body.lower()
    normalized_missing_fields = " ".join(missing_fields).lower()
    blocked_snippets = [
        "ti chiameremo",
        "il nostro team",
        "la tua categoria",
        "qual e la tua categoria",
        "qual è la tua categoria",
    ]
    if any(snippet in normalized_body for snippet in blocked_snippets):
        return False

    if context_label == "missing_collaborator_data":
        if missing_fields and not all(field.lower() in normalized_body for field in missing_fields):
            return False
        identity_document_snippets = [
            "documento di identita",
            "documento d'identita",
            "carta di identita",
            "carta d'identita",
        ]
        if (
            any(snippet in normalized_body for snippet in identity_document_snippets)
            and "document" not in normalized_missing_fields
        ):
            return False

    if context_label == "identity_document_followup":
        if "document" not in normalized_body:
            return False

    return True
