"""Backfill piano finanziario FAPI project 11 from uploaded Excel."""

from datetime import datetime
from glob import glob

import models
from database import SessionLocal
from services.piano_finanziario_parser import parse_piano_finanziario, resolve_modulo_formativo_id


PROJECT_ID = 11
UPLOAD_PATTERN = "/app/uploads/piani_finanziari/10_*.xlsx"


def _macrovoce(codice: str) -> str:
    c = (codice or "A")[0].upper()
    return c if c in "ABCD" else "A"


def _categoria(desc: str | None, materia: str | None) -> str:
    combined = f"{desc or ''} {materia or ''}".lower()
    if (materia or "").strip().lower().startswith("tutor"):
        return "tutoraggio"
    for kw, cat in [
        ("docenz", "docenza"),
        ("tutor", "tutoraggio"),
        ("progett", "progettazione"),
        ("material", "materiali_didattici"),
        ("aula", "aula"),
        ("attrezzat", "attrezzature"),
        ("certific", "certificazioni"),
        ("viaggio", "viaggi"),
        ("retribuz", "altro"),
        ("assicuraz", "altro"),
        ("promoz", "altro"),
        ("monitor", "altro"),
        ("coordinam", "coordinamento"),
        ("direzione", "coordinamento"),
    ]:
        if kw in combined:
            return cat
    return "altro"


def main() -> None:
    db = SessionLocal()
    try:
        project = db.query(models.Project).filter(models.Project.id == PROJECT_ID).first()
        if not project:
            raise RuntimeError(f"Project {PROJECT_ID} not found")

        files = sorted(glob(UPLOAD_PATTERN))
        if not files:
            raise RuntimeError(f"No Excel files found for pattern {UPLOAD_PATTERN}")
        parsed = parse_piano_finanziario(files[-1])

        piano = db.query(models.PianoFinanziario).filter(
            models.PianoFinanziario.progetto_id == PROJECT_ID,
            models.PianoFinanziario.tipo_fondo == "fapi",
        ).first()
        if not piano:
            now = datetime.now()
            piano = models.PianoFinanziario(
                progetto_id=PROJECT_ID,
                anno=now.year,
                ente_erogatore="FAPI",
                avviso=project.codice_fapi or "",
                tipo_fondo="fapi",
                nome=f"Piano Finanziario FAPI - {project.codice_fapi or project.name}",
                codice_piano=project.codice_fapi,
                budget_totale=0.0,
                budget_approvato=0.0,
                budget_utilizzato=0.0,
                budget_rimanente=0.0,
                data_inizio=project.start_date or now,
                data_fine=project.end_date or datetime(now.year + 1, 12, 31),
                stato="bozza",
            )
            db.add(piano)
            db.flush()
        else:
            db.query(models.VocePianoFinanziario).filter(
                models.VocePianoFinanziario.piano_id == piano.id
            ).delete(synchronize_session=False)

        created = 0
        linked = 0
        budget_totale = 0.0
        for voce_data in parsed.get("voci", []):
            codice = voce_data.get("voce_codice") or "A"
            desc = voce_data.get("voce_descrizione")
            materia = voce_data.get("materia")
            categoria = _categoria(desc, materia)
            ore = float(voce_data.get("ore_previste") or 0.0)
            importo = float(voce_data.get("importo_totale") or 0.0)
            if not importo and categoria == "docenza" and ore:
                importo = round(ore * 50.0, 2)
            tariffa = round(importo / ore, 2) if ore else 0.0
            modulo_id = resolve_modulo_formativo_id(db, project, voce_data)
            if modulo_id:
                linked += 1
            db.add(models.VocePianoFinanziario(
                piano_id=piano.id,
                modulo_formativo_id=modulo_id,
                macrovoce=_macrovoce(codice),
                voce_codice=codice,
                categoria=categoria,
                sottocategoria=desc,
                mansione_riferimento=materia,
                descrizione=voce_data.get("azienda"),
                progetto_label=voce_data.get("azienda"),
                ore_previste=ore,
                ore=ore,
                tariffa_oraria=tariffa,
                importo_preventivo=importo,
                stato="previsto",
            ))
            budget_totale += importo
            created += 1

        piano.budget_totale = round(budget_totale, 2)
        piano.budget_approvato = round(budget_totale, 2)
        piano.budget_rimanente = round(budget_totale - float(piano.budget_utilizzato or 0), 2)
        db.commit()
        print(f"project_id={PROJECT_ID} piano_id={piano.id} voci_create={created} modulo_linked={linked} budget_totale={piano.budget_totale}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
