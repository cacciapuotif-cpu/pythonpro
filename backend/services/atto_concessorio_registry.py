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
    etichetta_atto: str
    fornisce_ente_attuatore: bool
    fornisce_aziende_beneficiarie: bool
    etichetta_formulario: str = "Formulario"
    etichetta_piano_finanziario: str = "Piano finanziario"
    etichetta_codice_progetto: str = "Codice progetto"


REGISTRY: dict[str, FondoAttoConcessorio] = {
    "fapi": FondoAttoConcessorio(
        fondo="fapi",
        tipo_documento="convenzione",
        etichetta_atto="Convenzione",
        fornisce_ente_attuatore=True,
        fornisce_aziende_beneficiarie=True,
        etichetta_formulario="Formulario",
        etichetta_piano_finanziario="Piano Finanziario",
        etichetta_codice_progetto="Codice FAPI",
    ),
    "formazienda": FondoAttoConcessorio(
        fondo="formazienda",
        tipo_documento="atto_concessione",
        etichetta_atto="Atto di adesione (Allegato E)",
        fornisce_ente_attuatore=True,
        fornisce_aziende_beneficiarie=False,
        etichetta_formulario="Formulario (Allegato A)",
        etichetta_piano_finanziario="Piano Fin.",
        etichetta_codice_progetto="Codice pratica Formazienda",
    ),
    # Struttura predisposta su richiesta esplicita, senza campione del
    # documento e senza toccare il router fondimpresa_upload.py esistente
    # (che oggi non versiona documenti): nessun comportamento cambia per
    # Fondimpresa finche' non arriva un parser dedicato.
    "fondimpresa": FondoAttoConcessorio(
        fondo="fondimpresa",
        tipo_documento="atto_concessione",
        etichetta_atto="Lettera di ammissione",
        fornisce_ente_attuatore=True,
        fornisce_aziende_beneficiarie=False,
        # Fondimpresa non ha ancora un formulario dedicato (nessun parser):
        # lo slot formulario resta senza pulsante, questa etichetta non e'
        # mostrata. Il secondo pulsante di Fondimpresa e' un riepilogo Excel,
        # non un piano finanziario in senso stretto: l'etichetta riflette
        # cosa carica davvero il modale a cui e' collegato.
        etichetta_formulario="Formulario",
        etichetta_piano_finanziario="Excel Riepilogo",
        etichetta_codice_progetto="Codice pratica Fondimpresa",
    ),
}

_DEFAULT = FondoAttoConcessorio(
    fondo="altro",
    tipo_documento="convenzione",
    etichetta_atto="Convenzione",
    fornisce_ente_attuatore=True,
    fornisce_aziende_beneficiarie=True,
    etichetta_formulario="Formulario",
    etichetta_piano_finanziario="Piano finanziario",
    etichetta_codice_progetto="Codice progetto",
)


def for_ente_erogatore(ente_erogatore: str | None) -> FondoAttoConcessorio:
    chiave = (ente_erogatore or "").strip().lower()
    return REGISTRY.get(chiave, _DEFAULT)


def fornisce_aziende_beneficiarie(ente_erogatore: str | None) -> bool:
    return for_ente_erogatore(ente_erogatore).fornisce_aziende_beneficiarie
