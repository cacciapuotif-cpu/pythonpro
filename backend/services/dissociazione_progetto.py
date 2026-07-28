"""UX-8: guardie di dominio per la dissociazione di allievi e aziende da un progetto.

Il punto di questo modulo e' che le guardie stiano in UN posto solo. Prima di
UX-8 la dissociazione avveniva come effetto collaterale del PUT progetto
(replace secco della lista di id in `crud._sync_project_allievi`), quindi
bastava omettere un id per staccare un allievo che aveva gia' l'attestato,
senza controlli e senza traccia in audit.

Il modulo non conosce HTTP: restituisce blocchi, e chi chiama decide come
tradurli (409 nel router, ValueError-equivalente in crud).

Nota di dominio: non esiste una tabella di presenze degli allievi.
`attendances` traccia i collaboratori e i timesheet pendono da `assignment`,
non da `allievo`. Le uniche tracce di un allievo su un progetto sono la riga
`allievo_project` (ore frequentate, attestato) e `dati_retributivi`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from sqlalchemy.orm import Session

import models

# Codici di blocco: stabili, il frontend ci si appoggia per i messaggi.
BLOCCO_ATTESTATO = "attestato_emesso"
BLOCCO_ORE = "ore_frequentate"
BLOCCO_DATI_RETRIBUTIVI = "dati_retributivi"
BLOCCO_ALLIEVI_AZIENDA = "allievi_azienda_associati"


@dataclass(frozen=True)
class Blocco:
    codice: str
    messaggio: str
    forzabile: bool

    def as_dict(self) -> dict:
        return {
            "codice": self.codice,
            "messaggio": self.messaggio,
            "forzabile": self.forzabile,
        }


class DissociazioneBloccata(Exception):
    """Sollevata quando le guardie impediscono la dissociazione."""

    def __init__(self, blocchi: List[Blocco], *, entita: str, entita_id: int):
        self.blocchi = blocchi
        self.entita = entita
        self.entita_id = entita_id
        super().__init__("; ".join(b.messaggio for b in blocchi))

    @property
    def forzabile(self) -> bool:
        """Superabile solo se OGNI blocco lo e'."""
        return bool(self.blocchi) and all(b.forzabile for b in self.blocchi)

    def as_detail(self) -> dict:
        return {
            "errore": "dissociazione_bloccata",
            "entita": self.entita,
            "entita_id": self.entita_id,
            "forzabile": self.forzabile,
            "blocchi": [b.as_dict() for b in self.blocchi],
        }


def _nome_allievo(allievo: models.Allievo | None) -> str:
    if allievo is None:
        return "allievo"
    return " ".join(part for part in (allievo.nome, allievo.cognome) if part) or f"allievo {allievo.id}"


def blocchi_dissociazione_allievo(
    db: Session, project_id: int, allievo_id: int
) -> List[Blocco]:
    """Guardie che si oppongono a staccare `allievo_id` da `project_id`."""
    link = (
        db.query(models.AllievoProject)
        .filter(
            models.AllievoProject.project_id == project_id,
            models.AllievoProject.allievo_id == allievo_id,
        )
        .first()
    )
    if link is None:
        return []

    blocchi: List[Blocco] = []

    if link.attestato_emesso:
        blocchi.append(Blocco(
            codice=BLOCCO_ATTESTATO,
            messaggio=(
                "L'attestato e' gia' stato emesso per questo allievo su questo "
                "progetto: la dissociazione non e' consentita."
            ),
            forzabile=False,
        ))

    if link.ore_frequentate is not None and float(link.ore_frequentate) > 0:
        blocchi.append(Blocco(
            codice=BLOCCO_ORE,
            messaggio=(
                f"L'allievo ha {float(link.ore_frequentate):g} ore frequentate "
                "registrate su questo progetto."
            ),
            forzabile=True,
        ))

    dati_retributivi = (
        db.query(models.DatiRetributivi)
        .filter(
            models.DatiRetributivi.project_id == project_id,
            models.DatiRetributivi.allievo_id == allievo_id,
        )
        .count()
    )
    if dati_retributivi:
        blocchi.append(Blocco(
            codice=BLOCCO_DATI_RETRIBUTIVI,
            messaggio=(
                "Sono presenti dati retributivi (busta paga / RAL) per questo "
                "allievo su questo progetto."
            ),
            forzabile=True,
        ))

    return blocchi


def blocchi_dissociazione_azienda(
    db: Session, project_id: int, azienda_id: int
) -> List[Blocco]:
    """Guardie che si oppongono a staccare `azienda_id` da `project_id`.

    Niente cascata implicita: se l'azienda porta ancora suoi allievi sul
    progetto, prima si staccano quelli (uno per uno, con le loro guardie).
    """
    allievi = (
        db.query(models.Allievo)
        .join(
            models.AllievoProject,
            models.AllievoProject.allievo_id == models.Allievo.id,
        )
        .filter(
            models.AllievoProject.project_id == project_id,
            models.Allievo.azienda_cliente_id == azienda_id,
        )
        .all()
    )
    if not allievi:
        return []

    nomi = ", ".join(_nome_allievo(a) for a in allievi)
    return [Blocco(
        codice=BLOCCO_ALLIEVI_AZIENDA,
        messaggio=(
            f"L'azienda ha ancora {len(allievi)} allievo/i associati al progetto "
            f"({nomi}): dissociarli prima di staccare l'azienda."
        ),
        forzabile=False,
    )]


def verifica_dissociazione_allievo(
    db: Session, project_id: int, allievo_id: int, *, forza: bool = False
) -> None:
    """Solleva `DissociazioneBloccata` se le guardie non lo permettono."""
    blocchi = blocchi_dissociazione_allievo(db, project_id, allievo_id)
    if not blocchi:
        return
    errore = DissociazioneBloccata(blocchi, entita="allievo", entita_id=allievo_id)
    if forza and errore.forzabile:
        return
    raise errore


def verifica_dissociazione_azienda(
    db: Session, project_id: int, azienda_id: int, *, forza: bool = False
) -> None:
    blocchi = blocchi_dissociazione_azienda(db, project_id, azienda_id)
    if not blocchi:
        return
    errore = DissociazioneBloccata(blocchi, entita="azienda", entita_id=azienda_id)
    if forza and errore.forzabile:
        return
    raise errore
