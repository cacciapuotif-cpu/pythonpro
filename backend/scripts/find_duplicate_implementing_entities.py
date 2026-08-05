"""Report one-shot, sola lettura: enti attuatori duplicati.

Caso reale che l'ha motivato: il progetto FAPI MAXI COMMUNICATION punta a
"Next Group srl" (seed placeholder, partita_iva 00000000002), il progetto
Formazienda WHITE FORM punta a "NEXT GROUP S.R.L." (partita_iva reale
06615351217, creata dall'import Allegato E). Sono la stessa azienda: il
match in formazienda_upload.py._find_ente_in_db (partita_iva esatta, poi
un fallback a substring sui primi 20 caratteri di ragione_sociale) non
li accosta perche' la piva differisce e "srl"/"S.R.L." rompono il
substring.

Questo script raggruppa ImplementingEntity per partita_iva normalizzata E
per ragione_sociale normalizzata (uppercase, punteggiatura e forme
societarie rimosse) e segnala i gruppi con piu' di una riga. Zero
scritture: nessuna fusione automatica, la conferma resta della persona
che legge il report (vedi audit/ENTITY_DUPLICATES_REPORT.md).
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import models
from database import SessionLocal

REPORT_PATH = Path(__file__).resolve().parent.parent.parent / "audit" / "ENTITY_DUPLICATES_REPORT.md"

_FORME_SOCIETARIE = re.compile(
    r"\b(S\.?R\.?L\.?S?|S\.?P\.?A\.?|S\.?C\.?A\.?R\.?L\.?|S\.?N\.?C\.?|S\.?A\.?S\.?|SOCIETA'?\s+COOPERATIVA)\b",
    re.IGNORECASE,
)
_PUNTEGGIATURA = re.compile(r"[^\w\s]")
_SPAZI = re.compile(r"\s+")


def normalizza_ragione_sociale(ragione_sociale: str | None) -> str:
    """Uppercase, punteggiatura e forme societarie rimosse, spazi collassati.

    "Next Group srl" e "NEXT GROUP S.R.L." normalizzano entrambe a
    "NEXT GROUP": e' esattamente il caso che il match a substring in
    formazienda_upload.py non cattura.
    """
    testo = (ragione_sociale or "").upper()
    testo = _FORME_SOCIETARIE.sub(" ", testo)
    testo = _PUNTEGGIATURA.sub(" ", testo)
    testo = _SPAZI.sub(" ", testo).strip()
    return testo


def normalizza_partita_iva(partita_iva: str | None) -> str:
    return re.sub(r"\D", "", partita_iva or "")


@dataclass
class CandidatoDuplicato:
    id: int
    ragione_sociale: str
    partita_iva: str | None
    created_at: object
    progetti_collegati: int


def trova_gruppi_duplicati(session) -> dict[str, list[CandidatoDuplicato]]:
    """Ritorna {chiave_normalizzata: [candidati]} solo per gruppi con >1 riga.

    Raggruppa per ragione_sociale normalizzata; la partita_iva normalizzata
    e' inclusa nel report per contesto ma non usata per separare gruppi,
    perche' e' proprio quando le due piva DIFFERISCONO (un placeholder, una
    vera) che il duplicato sfugge al matching applicativo.
    """
    entita = session.query(models.ImplementingEntity).all()
    gruppi: dict[str, list[CandidatoDuplicato]] = defaultdict(list)

    for ente in entita:
        chiave = normalizza_ragione_sociale(ente.ragione_sociale)
        if not chiave:
            continue
        progetti_collegati = (
            session.query(models.Project)
            .filter(models.Project.ente_attuatore_id == ente.id)
            .count()
        )
        gruppi[chiave].append(
            CandidatoDuplicato(
                id=ente.id,
                ragione_sociale=ente.ragione_sociale,
                partita_iva=ente.partita_iva,
                created_at=ente.created_at,
                progetti_collegati=progetti_collegati,
            )
        )

    return {chiave: candidati for chiave, candidati in gruppi.items() if len(candidati) > 1}


def genera_report(gruppi: dict[str, list[CandidatoDuplicato]]) -> str:
    righe = [
        "# Report enti attuatori duplicati",
        "",
        "Generato da `backend/scripts/find_duplicate_implementing_entities.py`.",
        "Sola lettura: nessuna riga e' stata modificata o fusa. La fusione,",
        "se opportuna, va confermata manualmente dopo aver letto questo report.",
        "",
    ]

    if not gruppi:
        righe.append("Nessun duplicato rilevato.")
        return "\n".join(righe) + "\n"

    righe.append(f"**{len(gruppi)} gruppo/i con piu' di un record per la stessa azienda.**")
    righe.append("")

    for chiave, candidati in sorted(gruppi.items()):
        righe.append(f"## \"{chiave}\"")
        righe.append("")
        righe.append("| id | ragione_sociale | partita_iva | progetti collegati |")
        righe.append("|----|------------------|-------------|---------------------|")
        for candidato in sorted(candidati, key=lambda c: c.id):
            righe.append(
                f"| {candidato.id} | {candidato.ragione_sociale} | "
                f"{candidato.partita_iva or '—'} | {candidato.progetti_collegati} |"
            )
        righe.append("")

    return "\n".join(righe) + "\n"


def main() -> None:
    session = SessionLocal()
    try:
        gruppi = trova_gruppi_duplicati(session)
    finally:
        session.close()

    report = genera_report(gruppi)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report)
    print(f"Report scritto in {REPORT_PATH}")


if __name__ == "__main__":
    main()
