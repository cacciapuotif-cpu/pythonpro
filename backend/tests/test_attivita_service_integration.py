import json
from datetime import date, datetime
from pathlib import Path
import sys
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))
import auth
import models
from services.attivita import aggiorna_attivita, apply_piano_attivita, cambia_stato


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'attivita.db'}")
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    for table in (models.Collaborator.__table__, models.ImplementingEntity.__table__, models.Avviso.__table__, models.AvvisoRevisione.__table__, models.AvvisoScadenza.__table__, auth.User.__table__, models.Project.__table__, models.Playbook.__table__, models.PlaybookVersione.__table__, models.PlaybookVoce.__table__,
                  models.AgentRun.__table__, models.AgentSuggestion.__table__,
                  models.AttivitaOperativa.__table__, models.AttivitaEvento.__table__):
        table.create(engine, checkfirst=True)
    session = sessionmaker(bind=engine)(); yield session; session.close(); engine.dispose()


def user(db, role="operatore"):
    value = auth.User(username=f"{role}-a", email=f"{role}-a@example.test", hashed_password="x", role=role)
    db.add(value); db.commit(); return value


def suggestion(db, project_id, items):
    run = models.AgentRun(agent_type="activity_planner", entity_type="project", entity_id=project_id, status="completed")
    db.add(run); db.flush()
    value = models.AgentSuggestion(run_id=run.id, suggestion_type="piano_attivita", entity_type="project",
        entity_id=project_id, title="Piano", auto_fix_payload=json.dumps({"kind":"attivita_piano", "project_id":project_id, "attivita":items}))
    db.add(value); db.commit(); return value


def test_apply_is_idempotent_and_creates_creation_event(db):
    actor = user(db); project = models.Project(name="P"); db.add(project); db.commit()
    proposal = suggestion(db, project.id, [{"fase":"avvio", "titolo":"Checklist", "ordine":1}])
    assert apply_piano_attivita(db, proposal, user_id=actor.id) == {"create":1, "esistenti":0}
    assert apply_piano_attivita(db, proposal, user_id=actor.id) == {"create":0, "esistenti":1}
    activity = db.query(models.AttivitaOperativa).one()
    assert [event.tipo_evento for event in activity.eventi] == ["creata"]


def test_state_machine_completes_and_reopens_with_events(db):
    actor = user(db); project = models.Project(name="P"); db.add(project); db.commit()
    activity = models.AttivitaOperativa(project_id=project.id, fase="avvio", titolo="T", created_by_user_id=actor.id)
    db.add(activity); db.commit()
    cambia_stato(db, attivita_id=activity.id, nuovo_stato="completata", user_id=actor.id)
    assert activity.completata_da_user_id == actor.id and activity.completata_il is not None
    cambia_stato(db, attivita_id=activity.id, nuovo_stato="da_fare", user_id=actor.id)
    assert activity.completata_da_user_id is None
    assert [event.tipo_evento for event in activity.eventi] == ["stato_cambiato", "riaperta"]


def test_state_change_requires_authenticated_actor(db):
    project = models.Project(name="P"); db.add(project); db.commit()
    activity = models.AttivitaOperativa(project_id=project.id, fase="avvio", titolo="T")
    db.add(activity); db.commit()
    with pytest.raises(ValueError, match="attore|utente|obbligatorio"):
        cambia_stato(db, attivita_id=activity.id, nuovo_stato="in_corso", user_id=None)


def test_update_writes_deadline_assignee_and_note_events_atomically(db):
    actor = user(db)
    assignee = auth.User(
        username="assegnatario-a",
        email="assegnatario-a@example.test",
        hashed_password="x",
        role="operatore",
    )
    project = models.Project(name="P")
    db.add_all([assignee, project])
    db.commit()
    activity = models.AttivitaOperativa(
        project_id=project.id,
        fase="gestione",
        titolo="Aggiorna",
        created_by_user_id=actor.id,
    )
    db.add(activity)
    db.commit()

    aggiorna_attivita(
        db,
        attivita_id=activity.id,
        user_id=actor.id,
        scadenza=date(2026, 9, 30),
        assegnatario_user_id=assignee.id,
        note="Verificata",
    )

    db.refresh(activity)
    assert activity.scadenza == date(2026, 9, 30)
    assert activity.assegnatario_user_id == assignee.id
    assert activity.note == "Verificata"
    assert [event.tipo_evento for event in activity.eventi] == [
        "scadenza_modificata",
        "assegnata",
        "nota",
    ]
