"""Matching trasparente fra documenti di concessione e progetti esistenti."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import models


def _decimal(value):
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _candidate(project, *, confidenza: str, motivi: list[str]) -> dict:
    return {
        "project_id": project.id,
        "nome": project.name,
        "codice_fapi": project.codice_fapi,
        "confidenza": confidenza,
        "motivi": motivi,
    }


def trova_candidati(db, preview: dict) -> dict:
    """Match forte per codice; fallback triplo sempre sottoposto all'utente."""
    piano = preview.get("piano") or {}
    codice = (piano.get("codice_fapi") or "").strip()
    codici_figli = {
        str(value).strip()
        for value in (preview.get("codici_progetto") or [])
        if str(value).strip()
    }

    by_id: dict[int, dict] = {}
    if codice:
        for project in db.query(models.Project).filter(
            models.Project.codice_fapi == codice
        ).all():
            by_id[project.id] = _candidate(
                project,
                confidenza="esatta",
                motivi=["codice_piano"],
            )

    if codici_figli:
        rows = (
            db.query(models.Project)
            .join(
                models.ModuloFormativo,
                models.ModuloFormativo.project_id == models.Project.id,
            )
            .filter(models.ModuloFormativo.codice_progetto_fapi.in_(codici_figli))
            .distinct()
            .all()
        )
        for project in rows:
            if project.id in by_id:
                by_id[project.id]["motivi"].append("codice_progetto")
            else:
                by_id[project.id] = _candidate(
                    project,
                    confidenza="esatta",
                    motivi=["codice_progetto"],
                )

    if not by_id:
        ente_info = preview.get("ente_attuatore") or {}
        ente_id = ente_info.get("id")
        delibera_numero = piano.get("delibera_numero")
        delibera_data = piano.get("delibera_data")
        costo = _decimal(piano.get("costo_totale"))
        if ente_id and (delibera_numero or delibera_data) and costo is not None:
            for project in db.query(models.Project).filter(
                models.Project.ente_attuatore_id == ente_id
            ).all():
                delibera_match = (
                    (delibera_numero and project.delibera_numero == delibera_numero)
                    or (
                        delibera_data
                        and project.delibera_data
                        and project.delibera_data.isoformat() == str(delibera_data)
                    )
                )
                if delibera_match and _decimal(project.costo_totale) == costo:
                    by_id[project.id] = _candidate(
                        project,
                        confidenza="incerta",
                        motivi=["ente_attuatore", "delibera", "costo_totale"],
                    )

    candidates = list(by_id.values())
    exact = [c for c in candidates if c["confidenza"] == "esatta"]
    if len(exact) == 1 and len(candidates) == 1:
        stato = "esatto"
        selected_id = exact[0]["project_id"]
    elif candidates:
        stato = "incerto"
        selected_id = None
    else:
        stato = "nessuno"
        selected_id = None

    return {
        "stato": stato,
        "project_id": selected_id,
        "candidati": candidates,
    }
