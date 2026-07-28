"""UX-5 — semantica e coerenza delle date di progetto.

Le date amministrative del piano e quelle effettive delle attività formative
sono concetti distinti. Questo servizio è l'unico punto applicativo che decide
se una loro combinazione è coerente; API, import e futuri agenti devono
delegare qui invece di replicare confronti locali.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping


CAMPI_DATE_PROGETTO = (
    "data_approvazione",
    "data_avvio_piano",
    "data_termine_piano",
    "data_avvio_attivita_formative",
    "data_fine_attivita_formative",
    "data_termine_rendicontazione",
    "data_chiusura_effettiva",
)


def _giorno(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _valore(values: Mapping[str, Any] | Any, name: str) -> Any:
    if isinstance(values, Mapping):
        return values.get(name)
    return getattr(values, name, None)


def valida_date_progetto(
    values: Mapping[str, Any] | Any,
    *,
    richiedi_date_nuovo_attivo: bool = False,
) -> None:
    """Valida una fotografia completa delle date.

    La migration è additiva: i record legacy possono restare senza i nuovi
    campi. Solo la creazione di un nuovo progetto ``active`` pretende subito
    approvazione e avvio piano.
    """

    status = _valore(values, "status") or "active"
    data_approvazione = _giorno(_valore(values, "data_approvazione"))
    data_avvio_piano = _giorno(_valore(values, "data_avvio_piano"))
    data_termine_piano = _giorno(_valore(values, "data_termine_piano"))
    data_avvio_attivita = _giorno(
        _valore(values, "data_avvio_attivita_formative")
    )
    data_fine_attivita = _giorno(
        _valore(values, "data_fine_attivita_formative")
    )
    data_termine_rendicontazione = _giorno(
        _valore(values, "data_termine_rendicontazione")
    )
    data_chiusura = _giorno(_valore(values, "data_chiusura_effettiva"))

    if richiedi_date_nuovo_attivo and status == "active":
        mancanti = []
        if data_approvazione is None:
            mancanti.append("data approvazione")
        if data_avvio_piano is None:
            mancanti.append("data avvio piano")
        if mancanti:
            raise ValueError(
                "Per un nuovo progetto attivo sono obbligatorie: "
                + ", ".join(mancanti)
            )

    if (
        data_approvazione is not None
        and data_avvio_piano is not None
        and data_approvazione > data_avvio_piano
    ):
        raise ValueError(
            "La data di approvazione non può essere successiva alla data di avvio piano"
        )

    if (
        data_avvio_piano is not None
        and data_termine_piano is not None
        and data_avvio_piano > data_termine_piano
    ):
        raise ValueError(
            "Il termine del piano non può precedere la data di avvio piano"
        )

    if (
        data_avvio_attivita is not None
        and data_fine_attivita is not None
        and data_avvio_attivita > data_fine_attivita
    ):
        raise ValueError(
            "La fine delle attività formative non può precederne l'avvio"
        )

    if (
        data_avvio_piano is not None
        and data_avvio_attivita is not None
        and data_avvio_attivita < data_avvio_piano
    ):
        raise ValueError(
            "L'avvio delle attività formative non può precedere l'avvio del piano"
        )

    if (
        data_termine_piano is not None
        and data_fine_attivita is not None
        and data_fine_attivita > data_termine_piano
    ):
        raise ValueError(
            "La fine delle attività formative non può superare il termine del piano"
        )

    if (
        data_fine_attivita is not None
        and data_termine_rendicontazione is not None
        and data_termine_rendicontazione < data_fine_attivita
    ):
        raise ValueError(
            "Il termine di rendicontazione non può precedere la fine delle attività formative"
        )

    if (
        data_fine_attivita is not None
        and data_chiusura is not None
        and data_chiusura < data_fine_attivita
    ):
        raise ValueError(
            "La data di chiusura effettiva non può precedere la fine delle attività formative"
        )


def snapshot_date_progetto(project: Any, updates: Mapping[str, Any] | None = None) -> dict:
    """Fotografia completa per validare un update parziale senza penalizzare i legacy."""

    result = {
        name: getattr(project, name, None)
        for name in (*CAMPI_DATE_PROGETTO, "status")
    }
    result.update(updates or {})
    return result
