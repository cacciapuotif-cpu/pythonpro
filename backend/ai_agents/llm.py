from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class AgentLlmResult:
    subject: str
    body: str
    provider: str
    model: Optional[str] = None
    raw_text: Optional[str] = None


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

    context_instructions = _build_mail_context_instructions(
        context_label=context_label,
        missing_fields=missing_fields or [],
        days_to_expiry=days_to_expiry,
    )
    system_prompt = (
        "Sei un assistente per comunicazioni amministrative di un gestionale HR italiano. "
        "Scrivi email in italiano corretto, naturale, professionale e sintetico. "
        "Non inventare dati, ruoli, scadenze, procedure o riferimenti normativi non presenti nel contesto. "
        "Non fare domande inutili e non aggiungere firme generiche tipo 'Il nostro team'. "
        "Mantieni il focus solo sulla richiesta amministrativa. "
        "Rispondi esclusivamente in JSON valido con chiavi stringa subject e body."
    )
    user_prompt = (
        "Genera una bozza email migliorata per recupero dati o documenti.\n"
        "Vincoli obbligatori:\n"
        "- usa un saluto iniziale con il nome del collaboratore\n"
        "- massimo 3 paragrafi brevi\n"
        "- indica con precisione cosa manca o cosa deve essere aggiornato\n"
        "- chiudi con una call to action semplice: chiedi di rispondere inviando i dati o il documento aggiornato\n"
        "- nessuna firma finale, nessun slogan, nessuna frase autocelebrativa\n"
        "- non chiedere informazioni diverse da quelle presenti nel contesto\n\n"
        f"Istruzioni specifiche:\n{context_instructions}\n\n"
        f"Contesto strutturato:\n{json.dumps(prompt_payload, ensure_ascii=True, default=str)}\n\n"
        'Formato atteso:\n{"subject":"...","body":"..."}'
    )

    try:
        result: Optional[AgentLlmResult] = None
        if config.provider == "ollama":
            result = _call_ollama(config, system_prompt=system_prompt, user_prompt=user_prompt)
        elif config.provider == "openclaw":
            result = _call_openclaw(config, system_prompt=system_prompt, user_prompt=user_prompt)
        if result and _is_mail_copy_acceptable(
            context_label=context_label,
            body=result.body,
            missing_fields=missing_fields or [],
        ):
            return result
        logger.warning("LLM agent fallback attivato su provider %s: output non conforme ai controlli minimi", config.provider)
    except Exception as exc:
        logger.warning("LLM agent fallback attivato su provider %s: %s", config.provider, exc)
    return None


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
    subject, body = _normalize_mail_copy(parsed.get("subject"), parsed.get("body"))
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

    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
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
    parsed = _parse_json_object(raw_text)
    subject, body = _normalize_mail_copy(parsed.get("subject"), parsed.get("body"))
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
    if not parsed.get("subject") or not parsed.get("body"):
        raise ValueError("Risposta LLM JSON priva di subject/body")
    return parsed


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
        if "documento" in normalized_body and "document" not in " ".join(missing_fields).lower():
            return False

    if context_label == "identity_document_followup":
        if "document" not in normalized_body:
            return False

    return True
