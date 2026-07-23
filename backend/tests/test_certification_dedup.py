"""
B6a — dedup strutturato e batch nel certification_agent.

Copre:
- il bug di dedup su substring JSON (project.id substring di un altro id/valore
  nel payload → falso dedup), ora risolto con chiave esatta (allievo_id, project_id);
- il dedup esatto legittimo (stesso allievo+progetto già proposto → saltato);
- assenza di N+1: il numero di query non cresce col numero di link.
"""
import json
from datetime import datetime

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

import auth
import models
from database import Base
from ai_agents.certification_agent import collect_certification_suggestions


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        auth.User.__table__,
        models.Collaborator.__table__,
        models.Project.__table__,
        models.Assignment.__table__,
        models.Allievo.__table__,
        models.AllievoProject.__table__,
        models.AgentRun.__table__,
        models.AgentSuggestion.__table__,
    ])
    return Session(engine)


def _add_pending_suggestion(db, allievo_id, project_id):
    run = models.AgentRun(agent_type="certification", status="completed")
    db.add(run)
    db.flush()
    db.add(models.AgentSuggestion(
        run_id=run.id,
        entity_type="allievo_project", entity_id=allievo_id,
        suggestion_type="attestato_pronto", status="pending",
        title="Attestato pronto",
        payload=json.dumps({"allievo_id": allievo_id, "project_id": project_id}),
    ))


def _progetto_con_docente(db, project_id, name):
    project = models.Project(id=project_id, name=name, status="active")
    collaborator = models.Collaborator(
        first_name="Doc", last_name=str(project_id),
        email=f"doc{project_id}@example.com",
        fiscal_code=f"DCNNTE80A01H5{project_id:03d}", is_active=True,
    )
    db.add_all([project, collaborator])
    db.flush()
    db.add(models.Assignment(
        collaborator_id=collaborator.id, project_id=project.id,
        role="Docente", assigned_hours=100.0,
        start_date=datetime(2026, 1, 1), end_date=datetime(2026, 12, 31),
        hourly_rate=50.0, is_active=True,
    ))
    return project


def test_dedup_non_confonde_project_id_substring():
    """Suggestion pending per (allievo, progetto 15) NON deve dedupare lo stesso
    allievo nel progetto 5 (prima: payload.contains('5') matchava '15')."""
    db = make_db()
    allievo = models.Allievo(id=1, nome="Anna", cognome="Verdi")
    db.add(allievo)
    _progetto_con_docente(db, 5, "Corso A")
    _progetto_con_docente(db, 15, "Corso B")
    db.flush()
    for pid in (5, 15):
        db.add(models.AllievoProject(allievo_id=1, project_id=pid, ore_frequentate=80.0))
    # suggestion esistente solo per progetto 15
    _add_pending_suggestion(db, allievo_id=1, project_id=15)
    db.commit()

    result = collect_certification_suggestions(db)

    proposti = {s["payload"]["project_id"] for s in result["suggestions"]}
    # progetto 5 deve essere proposto (non falsamente dedupato); 15 no (già proposto)
    assert 5 in proposti
    assert 15 not in proposti


def test_dedup_esatto_salta_gia_proposto():
    db = make_db()
    allievo = models.Allievo(id=1, nome="Anna", cognome="Verdi")
    db.add(allievo)
    _progetto_con_docente(db, 7, "Corso")
    db.flush()
    db.add(models.AllievoProject(allievo_id=1, project_id=7, ore_frequentate=80.0))
    _add_pending_suggestion(db, allievo_id=1, project_id=7)
    db.commit()

    result = collect_certification_suggestions(db)
    assert result["suggestions"] == []


def test_nessun_n_plus_1_sui_link():
    """Il conteggio query non deve crescere col numero di link (batch)."""
    def _conta_query(n_link):
        db = make_db()
        _progetto_con_docente(db, 1, "Corso")
        db.flush()
        for i in range(n_link):
            a = models.Allievo(id=100 + i, nome=f"A{i}", cognome="X")
            db.add(a)
            db.flush()
            db.add(models.AllievoProject(allievo_id=a.id, project_id=1, ore_frequentate=80.0))
        db.commit()
        counter = {"n": 0}
        engine = db.get_bind()

        def _before(conn, cursor, statement, params, context, executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                counter["n"] += 1

        event.listen(engine, "before_cursor_execute", _before)
        try:
            collect_certification_suggestions(db)
        finally:
            event.remove(engine, "before_cursor_execute", _before)
        return counter["n"]

    q1 = _conta_query(1)
    q5 = _conta_query(5)
    # batch: stesso numero di query con 1 o 5 link (nessun N+1)
    assert q1 == q5, f"N+1 sospetto: {q1} query con 1 link, {q5} con 5 link"
