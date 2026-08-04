"""Cosa fornisce l'atto concessorio di ciascun fondo.

Il flusso di Delivery presumeva che l'atto concessorio contenesse sempre
ente + aziende beneficiarie: vero per la convenzione FAPI, falso per
l'Atto di adesione Formazienda (Allegato E), che porta l'ente ma nessuna
azienda. Questa dichiarazione per fondo e' quello che guida lo sblocco
selettivo della Delivery, non un'assunzione fissa nel codice del router.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FondoAttoConcessorio:
    fondo: str
    tipo_documento: str
    etichetta: str
    fornisce_ente_attuatore: bool
    fornisce_aziende_beneficiarie: bool


REGISTRY: dict[str, FondoAttoConcessorio] = {
    "fapi": FondoAttoConcessorio(
        fondo="fapi",
        tipo_documento="convenzione",
        etichetta="Convenzione",
        fornisce_ente_attuatore=True,
        fornisce_aziende_beneficiarie=True,
    ),
    "formazienda": FondoAttoConcessorio(
        fondo="formazienda",
        tipo_documento="atto_concessione",
        etichetta="Atto di adesione (Allegato E)",
        fornisce_ente_attuatore=True,
        fornisce_aziende_beneficiarie=False,
    ),
    # Struttura predisposta su richiesta esplicita, senza campione del
    # documento e senza toccare il router fondimpresa_upload.py esistente
    # (che oggi non versiona documenti): nessun comportamento cambia per
    # Fondimpresa finche' non arriva un parser dedicato.
    "fondimpresa": FondoAttoConcessorio(
        fondo="fondimpresa",
        tipo_documento="atto_concessione",
        etichetta="Lettera di ammissione",
        fornisce_ente_attuatore=True,
        fornisce_aziende_beneficiarie=False,
    ),
}

_DEFAULT = FondoAttoConcessorio(
    fondo="altro",
    tipo_documento="convenzione",
    etichetta="Convenzione",
    fornisce_ente_attuatore=True,
    fornisce_aziende_beneficiarie=True,
)


def for_ente_erogatore(ente_erogatore: str | None) -> FondoAttoConcessorio:
    chiave = (ente_erogatore or "").strip().lower()
    return REGISTRY.get(chiave, _DEFAULT)


def fornisce_aziende_beneficiarie(ente_erogatore: str | None) -> bool:
    return for_ente_erogatore(ente_erogatore).fornisce_aziende_beneficiarie
