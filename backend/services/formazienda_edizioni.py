"""Materializza in modo idempotente le edizioni formative Formazienda."""

from __future__ import annotations

import re
from decimal import Decimal

from sqlalchemy.orm import Session

import models


_CODICE_EDIZIONE = re.compile(r"^FA-(\d+)-ED(\d{2})$")


def _normalizza_identificativo(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def _aziende_del_progetto(db: Session, project_id: int) -> dict[str, models.AziendaCliente]:
    aziende = (
        db.query(models.AziendaCliente)
        .join(
            models.AziendaClienteProjectLink,
            models.AziendaClienteProjectLink.azienda_cliente_id == models.AziendaCliente.id,
        )
        .filter(models.AziendaClienteProjectLink.project_id == project_id)
        .all()
    )
    result: dict[str, models.AziendaCliente] = {}
    for azienda in aziende:
        for value in (azienda.partita_iva, azienda.codice_fiscale):
            key = _normalizza_identificativo(value)
            if key:
                result[key] = azienda
    return result


def _mappatura_edizioni(
    progetto_formativo: dict,
    finanziamenti_per_impresa: list[dict],
    aziende_by_identifier: dict[str, models.AziendaCliente],
) -> tuple[list[models.AziendaCliente | None], list[str]]:
    """Associa azienda-edizione solo quando tutte le quadrature sono provate."""
    warnings: list[str] = []
    edizioni = int(progetto_formativo.get("edizioni") or 0)
    costo_edizione = progetto_formativo.get("costo_finanziamento_per_edizione")
    if edizioni <= 0:
        return [], ["Numero edizioni mancante o non valido: nessuna edizione materializzata"]
    if len(finanziamenti_per_impresa) != edizioni:
        return [None] * edizioni, [
            f"Associazione azienda-edizione non applicata: {edizioni} edizioni ma "
            f"{len(finanziamenti_per_impresa)} righe di finanziamento per impresa"
        ]

    aziende: list[models.AziendaCliente | None] = []
    ids_visti: set[int] = set()
    for riga in finanziamenti_per_impresa:
        identificativo = _normalizza_identificativo(riga.get("identificativo_fiscale"))
        azienda = aziende_by_identifier.get(identificativo)
        finanziamento = riga.get("finanziamento")
        if azienda is None:
            warnings.append(
                f"Impresa del riepilogo non riconducibile al progetto: {identificativo or 'identificativo vuoto'}"
            )
        elif azienda.id in ids_visti:
            warnings.append(f"Impresa ripetuta nel riepilogo edizioni: {azienda.ragione_sociale}")
        elif costo_edizione is not None and finanziamento is not None and abs(
            Decimal(str(costo_edizione)) - Decimal(str(finanziamento))
        ) > Decimal("0.50"):
            warnings.append(
                f"Finanziamento impresa non coincide col costo edizione per {azienda.ragione_sociale}"
            )
        aziende.append(azienda)
        if azienda is not None:
            ids_visti.add(azienda.id)

    # Una mappatura parziale sembra attendibile ma non lo e': se una sola riga
    # non quadra, si materializzano comunque le edizioni senza attribuire
    # aziende arbitrarie.
    if warnings or len(ids_visti) != edizioni:
        return [None] * edizioni, warnings or [
            "Associazione azienda-edizione non univoca: edizioni create senza azienda"
        ]
    return aziende, []


def sincronizza_edizioni_formazienda(
    db: Session,
    *,
    project_id: int,
    progetti_formativi: list[dict],
    riepilogo: dict,
) -> dict:
    """Crea/aggiorna una riga ``ModuloFormativo`` per ogni edizione dichiarata."""
    aziende_by_identifier = _aziende_del_progetto(db, project_id)
    finanziamenti = list(riepilogo.get("finanziamenti_per_impresa") or [])
    warnings: list[str] = []
    expected_codes: set[str] = set()
    created = 0
    updated = 0

    # Rimuove esclusivamente le righe create dal vecchio importatore
    # Formazienda: nessun codice, modalita' tecnica nota e obiettivo che
    # iniziava con "Edizioni:". I moduli manuali restano intatti.
    legacy = (
        db.query(models.ModuloFormativo)
        .filter(
            models.ModuloFormativo.project_id == project_id,
            models.ModuloFormativo.codice_progetto_fapi.is_(None),
            models.ModuloFormativo.modalita_erogazione == "mista_aula_toj",
            models.ModuloFormativo.tipo_attivita == "formativa",
            models.ModuloFormativo.obiettivo.like("Edizioni:%"),
        )
        .all()
    )
    for modulo in legacy:
        db.delete(modulo)

    for project_index, progetto in enumerate(progetti_formativi, start=1):
        numero_raw = str(progetto.get("numero") or project_index)
        numero = int(numero_raw) if numero_raw.isdigit() else project_index
        edizioni = int(progetto.get("edizioni") or 0)
        if edizioni <= 0:
            warnings.append(
                f"Progetto formativo {numero}: numero edizioni mancante o non valido"
            )
            continue

        if len(progetti_formativi) == 1:
            aziende_edizioni, mapping_warnings = _mappatura_edizioni(
                progetto, finanziamenti, aziende_by_identifier,
            )
            warnings.extend(mapping_warnings)
        else:
            aziende_edizioni = [None] * edizioni
            warnings.append(
                f"Progetto formativo {numero}: associazione azienda-edizione non automatica "
                "in un formulario con piu' progetti formativi"
            )

        for edition_index in range(1, edizioni + 1):
            code = f"FA-{numero}-ED{edition_index:02d}"
            expected_codes.add(code)
            azienda = aziende_edizioni[edition_index - 1]
            title = progetto.get("titolo") or "Progetto Formazienda"
            values = {
                "azienda_beneficiaria_id": azienda.id if azienda else None,
                "titolo_modulo": f"{title} - Edizione {edition_index:02d}/{edizioni:02d}",
                "materia": progetto.get("tematica"),
                "modalita_erogazione": "mista_aula_toj",
                "tipo_attivita": "formativa",
                "ore_previste": progetto.get("ore_formazione") or 0,
                "obiettivo": (
                    f"Formazienda; progetto {numero}; edizione {edition_index}/{edizioni}; "
                    f"Modalita: {progetto.get('modalita_attuazione')}; "
                    f"Finanziamento/edizione: {progetto.get('costo_finanziamento_per_edizione')}"
                ),
            }
            modulo = (
                db.query(models.ModuloFormativo)
                .filter(
                    models.ModuloFormativo.project_id == project_id,
                    models.ModuloFormativo.codice_progetto_fapi == code,
                )
                .first()
            )
            if modulo is None:
                db.add(models.ModuloFormativo(
                    project_id=project_id,
                    codice_progetto_fapi=code,
                    **values,
                ))
                created += 1
            else:
                for field, value in values.items():
                    setattr(modulo, field, value)
                updated += 1

    stale = (
        db.query(models.ModuloFormativo)
        .filter(
            models.ModuloFormativo.project_id == project_id,
            models.ModuloFormativo.codice_progetto_fapi.like("FA-%-ED__"),
        )
        .all()
    )
    stale = [m for m in stale if _CODICE_EDIZIONE.match(m.codice_progetto_fapi or "") and m.codice_progetto_fapi not in expected_codes]
    for modulo in stale:
        db.delete(modulo)

    return {
        "moduli_creati": created,
        "moduli_aggiornati": updated,
        "moduli_rimossi": len(legacy) + len(stale),
        "edizioni_totali": len(expected_codes),
        "warnings": warnings,
    }
