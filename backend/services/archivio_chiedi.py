"""Chiedi all'archivio (FASE E3, Task E3.2).

Orchestrazione onesta di una domanda in linguaggio naturale sull'archivio
avvisi. Tre regole non negoziabili, ciascuna con test dedicato:

1. **Retrieval prima di tutto.** Si esegue sempre ``search_archivio``. Se non
   restituisce alcun passaggio -> ``stato="non_presente"``, ``risposta=None``
   e **l'LLM non viene mai interpellato**: non si inventa una risposta su un
   archivio che non contiene nulla di pertinente.

2. **Citazioni obbligatorie e verificate lato server.** Il prompt impone
   all'LLM di rispondere SOLO dai passaggi forniti e di citare esclusivamente
   gli identificatori elencati. Alla ricezione, ogni id citato viene
   riconfrontato con il set realmente recuperato: se anche una sola citazione
   punta a un id fuori dal retrieval (o la risposta e' priva di citazioni /
   di testo), la risposta viene **scartata** e si degrada onestamente.

3. **La ricerca funziona sempre.** Se l'LLM e' disabilitato, giu' o in
   timeout (``call_ollama_json`` solleva), ``stato="degradato"``,
   ``risposta=None`` e si restituiscono i soli risultati di ricerca.

Servizio puro: nessuna dipendenza dal router. Il router serializza l'esito
verso ``schemas.ArchivioChiediResponse``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from ai_agents.llm import call_ollama_json, probe_agent_llm_health
from services.archivio_search import RisultatoArchivio, search_archivio

logger = logging.getLogger(__name__)

STATO_OK = "ok"
STATO_NON_PRESENTE = "non_presente"
STATO_DEGRADATO = "degradato"

_MAX_PASSAGGI = 8

SYSTEM_PROMPT = (
    "Sei un assistente esperto della formazione finanziata italiana. Rispondi "
    "ESCLUSIVAMENTE sulla base dei passaggi dell'archivio avvisi forniti "
    "nell'elenco. Regole non negoziabili:\n"
    "1. Usa solo le informazioni contenute nei passaggi elencati. Non usare "
    "conoscenza esterna, non inventare, non estrapolare oltre il testo.\n"
    "2. Ogni affermazione della risposta deve essere sostenuta da almeno un "
    "passaggio, citato tramite il suo identificatore fra parentesi quadre.\n"
    "3. Cita SOLO gli identificatori presenti nell'elenco fornito. Non "
    "inventare identificatori.\n"
    "4. Se i passaggi non contengono elementi per rispondere, restituisci "
    "risposta vuota e citazioni vuote.\n"
    "Rispondi in italiano. Restituisci SOLO un oggetto JSON con esattamente "
    'questo schema: {"risposta": "<testo>", "citazioni": ["<id>", ...]} dove '
    "ogni elemento di citazioni e' esattamente uno degli identificatori "
    "forniti (stringa)."
)


@dataclass(frozen=True)
class ChiediArchivioEsito:
    stato: str
    risposta: Optional[str]
    citazioni: list[RisultatoArchivio] = field(default_factory=list)
    risultati: list[RisultatoArchivio] = field(default_factory=list)


def _passage_id(r: RisultatoArchivio) -> str:
    """Identificatore stabile e non ambiguo di un passaggio recuperato.

    I namespace (regola/conoscenza/esito) sono separati dal prefisso della
    fonte: ``regola:5`` e ``conoscenza:5`` non collidono.
    """
    if r.regola_id is not None:
        return f"regola:{r.regola_id}"
    if r.conoscenza_id is not None:
        return f"conoscenza:{r.conoscenza_id}"
    if r.esito_id is not None:
        return f"esito:{r.esito_id}"
    return f"avviso:{r.avviso_id}"


def _build_user_prompt(domanda: str, risultati: list[RisultatoArchivio]) -> str:
    righe = ["DOMANDA:", domanda.strip(), "", "PASSAGGI DISPONIBILI:"]
    for r in risultati:
        rif = f", {r.riferimento_articolo}" if r.riferimento_articolo else ""
        righe.append(
            f"[{_passage_id(r)}] (Avviso: {r.avviso_titolo}{rif}) {r.estratto}"
        )
    righe.append("")
    righe.append(
        "Rispondi citando solo gli identificatori fra parentesi quadre qui "
        "sopra."
    )
    return "\n".join(righe)


def _normalizza_citazioni(raw) -> list[str]:
    """Estrae la lista di id citati dall'output LLM, tollerante sul formato.

    Accetta liste di stringhe (formato richiesto) e, per robustezza, liste di
    oggetti con chiave ``id``/``passage_id``/``identificatore``.
    """
    if not isinstance(raw, list):
        return []
    ids: list[str] = []
    for elem in raw:
        if isinstance(elem, str):
            valore = elem.strip()
        elif isinstance(elem, dict):
            valore = str(
                elem.get("id")
                or elem.get("passage_id")
                or elem.get("identificatore")
                or ""
            ).strip()
        else:
            valore = str(elem).strip()
        if valore:
            ids.append(valore)
    return ids


def chiedi_archivio(
    db: Session,
    domanda: str,
    *,
    avviso_id: Optional[int] = None,
    tipo_fondo: Optional[str] = None,
    limit: int = 8,
) -> ChiediArchivioEsito:
    """Risponde a ``domanda`` restando ancorato all'archivio."""
    # or_fallback=True: la domanda e' in linguaggio naturale (verbosa). Il
    # retrieval a due stadi prova prima l'AND (precisione) e ripiega sull'OR dei
    # soli termini della domanda se l'AND non recupera nulla, senza inventare
    # risultati. Le 3 regole di onesta' restano intatte: se anche l'OR e' vuoto
    # -> `non_presente` e l'LLM non viene interpellato.
    risultati = search_archivio(
        db,
        domanda,
        avviso_id=avviso_id,
        tipo_fondo=tipo_fondo,
        limit=limit,
        or_fallback=True,
    )

    # Regola 1: nessun passaggio -> nessuna chiamata all'LLM.
    if not risultati:
        return ChiediArchivioEsito(
            stato=STATO_NON_PRESENTE, risposta=None, citazioni=[], risultati=[]
        )

    passaggi = risultati[:_MAX_PASSAGGI]
    user_prompt = _build_user_prompt(domanda, passaggi)

    # Regola 3: la ricerca funziona sempre; l'LLM e' un extra. Se e' giu',
    # disabilitato o in timeout, call_ollama_json solleva e si degrada.
    try:
        parsed = call_ollama_json(
            system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt
        )
    except Exception as exc:  # RuntimeError (disabilitato), timeout, JSON, ...
        motivo = _degrado_detail()
        logger.warning(
            "chiedi-archivio: LLM non disponibile (%s); degrado ai soli "
            "risultati di ricerca [%s]",
            exc.__class__.__name__,
            motivo,
        )
        return ChiediArchivioEsito(
            stato=STATO_DEGRADATO, risposta=None, citazioni=[], risultati=risultati
        )

    risposta = str(parsed.get("risposta") or "").strip()
    citazioni_ids = _normalizza_citazioni(parsed.get("citazioni"))

    id_validi = {_passage_id(r): r for r in passaggi}

    # Regola 2: risposta senza testo o senza citazioni -> non affidabile.
    if not risposta or not citazioni_ids:
        logger.warning(
            "chiedi-archivio: risposta LLM priva di testo o citazioni; degrado"
        )
        return ChiediArchivioEsito(
            stato=STATO_DEGRADATO, risposta=None, citazioni=[], risultati=risultati
        )

    # Regola 2: ogni id citato DEVE esistere nel retrieval, altrimenti scarto.
    fuori_retrieval = [cid for cid in citazioni_ids if cid not in id_validi]
    if fuori_retrieval:
        logger.warning(
            "chiedi-archivio: risposta LLM scartata, citazioni fuori "
            "retrieval=%s; degrado ai soli risultati di ricerca",
            json.dumps(fuori_retrieval, ensure_ascii=True),
        )
        return ChiediArchivioEsito(
            stato=STATO_DEGRADATO, risposta=None, citazioni=[], risultati=risultati
        )

    # Citazioni valide: costruite dai passaggi realmente recuperati, senza
    # duplicati, nell'ordine del retrieval.
    citati = set(citazioni_ids)
    citazioni = [r for r in passaggi if _passage_id(r) in citati]

    return ChiediArchivioEsito(
        stato=STATO_OK,
        risposta=risposta,
        citazioni=citazioni,
        risultati=risultati,
    )


def _degrado_detail() -> str:
    """Dettaglio di salute LLM per il log (riusa probe_agent_llm_health)."""
    try:
        return probe_agent_llm_health().detail
    except Exception:  # pragma: no cover - il probe non deve mai far fallire
        return "stato LLM non determinabile"
