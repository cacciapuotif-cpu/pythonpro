"""Workflow persistente e apply umano end-to-end per i due agenti ATT."""

from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import auth
import models
from agent_workflows import run_agent_workflow
from services.suggestion_apply import apply_suggestion


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'attivita-workflow.db'}")
    event.listen(
        engine,
        "connect",
        lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"),
    )
    for table in (
        models.Collaborator.__table__,
        models.ImplementingEntity.__table__,
        auth.User.__table__,
        models.AgentRun.__table__,
        models.AgentSuggestion.__table__,
        models.AuditLog.__table__,
        models.ContractTemplate.__table__,
        models.Avviso.__table__,
        models.AvvisoRevisione.__table__,
        models.AvvisoScadenza.__table__,
        models.AvvisoDocumento.__table__,
        models.Project.__table__,
        models.Playbook.__table__,
        models.PlaybookVersione.__table__,
        models.PlaybookVoce.__table__,
        models.AttivitaOperativa.__table__,
        models.AttivitaEvento.__table__,
    ):
        table.create(bind=engine, checkfirst=True)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def _actor(db):
    actor = auth.User(
        username="workflow-attivita",
        email="workflow-attivita@example.test",
        hashed_password="not-used",
        role="admin",
        is_active=True,
    )
    db.add(actor)
    db.commit()
    return actor


def _avviso_revision(db, actor):
    avviso = models.Avviso(
        codice="ATT-1/2026",
        ente_erogatore="FAPI",
        fondo="fapi",
        numero="1",
        anno=2026,
        titolo="Avviso ATT",
        stato="attivo",
    )
    db.add(avviso)
    db.flush()
    revision = models.AvvisoRevisione(
        avviso_id=avviso.id,
        numero_revisione=1,
        titolo="Avviso ATT revisione 1",
        stato_estrazione="estratto",
        created_by_user_id=actor.id,
    )
    db.add(revision)
    db.flush()
    avviso.revisione_corrente_id = revision.id
    db.commit()
    return avviso, revision


def test_activity_planner_workflow_persists_proposal_then_human_apply(
    db, monkeypatch
):
    monkeypatch.setenv("AGENTS_ENABLED", "true")
    monkeypatch.setenv("AGENT_ACTIVITY_PLANNER_ENABLED", "true")
    actor = _actor(db)
    avviso, revision = _avviso_revision(db, actor)
    project = models.Project(
        name="Progetto planner",
        avviso_id=avviso.id,
        avviso_revisione_id=revision.id,
    )
    deadline = models.AvvisoScadenza(
        avviso_revisione_id=revision.id,
        tipo="avvio",
        data=datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc),
        descrizione="Avviare il progetto",
        tassativa=True,
        testo_originale="Avvio entro il 30 settembre 2026",
        stato="validata",
        validata_da_user_id=actor.id,
        validata_il=datetime.now(timezone.utc),
    )
    db.add_all([project, deadline])
    db.commit()

    run = run_agent_workflow(
        db,
        agent_type="activity_planner",
        entity_type="project",
        entity_id=project.id,
        requested_by_user_id=actor.id,
    )

    assert run.status == "completed"
    assert db.query(models.AttivitaOperativa).count() == 0
    suggestion = db.query(models.AgentSuggestion).filter_by(run_id=run.id).one()
    assert suggestion.status == "pending"
    assert suggestion.suggestion_type == "piano_attivita"

    result = apply_suggestion(db, suggestion, user_id=actor.id)

    assert result == {"create": 1, "esistenti": 0}
    activity = db.query(models.AttivitaOperativa).one()
    assert activity.scadenza.isoformat() == "2026-09-30"
    assert activity.tassativa is True
    assert activity.created_by_user_id == actor.id
    assert [item.tipo_evento for item in activity.eventi] == ["creata"]


def test_procedure_extractor_workflow_persists_proposal_then_human_apply(
    db, tmp_path, monkeypatch
):
    from ai_agents import procedure_extractor

    monkeypatch.setenv("AGENTS_ENABLED", "true")
    monkeypatch.setenv("AGENT_PROCEDURE_EXTRACTOR_ENABLED", "true")
    monkeypatch.setattr(
        procedure_extractor,
        "call_ollama_json",
        lambda **_: {
            "voci": [
                {
                    "fase": "gestione",
                    "titolo": "Controllare il registro",
                    "descrizione": "Controllo mensile",
                    "tipo_contenuto": "attivita_semplice",
                    "testo_originale": "Il registro deve essere controllato ogni mese.",
                    "riferimento_articolo": "Par. 4",
                    "confidence": 0.81,
                }
            ]
        },
    )
    actor = _actor(db)
    avviso, revision = _avviso_revision(db, actor)
    source = tmp_path / "manuale.md"
    source.write_text(
        "# Gestione\n\nIl registro deve essere controllato ogni mese.\n",
        encoding="utf-8",
    )
    document = models.AvvisoDocumento(
        avviso_id=avviso.id,
        avviso_revisione_id=revision.id,
        tipo="manuale_gestione",
        original_filename="manuale.md",
        file_path=str(source),
        mime_type="text/markdown",
        sha256="a" * 64,
        uploaded_by_user_id=actor.id,
    )
    db.add(document)
    db.commit()

    run = run_agent_workflow(
        db,
        agent_type="procedure_extractor",
        entity_type="avviso_documento",
        entity_id=document.id,
        requested_by_user_id=actor.id,
    )

    assert run.status == "completed"
    assert db.query(models.PlaybookVoce).count() == 0
    suggestion = db.query(models.AgentSuggestion).filter_by(run_id=run.id).one()
    assert suggestion.status == "pending"

    result = apply_suggestion(db, suggestion, user_id=actor.id)

    assert result["applied"] and result["skipped"] == []
    playbook = db.query(models.Playbook).one()
    assert playbook.fondo == "fapi"
    assert playbook.ente_erogatore == "FAPI"
    voce = db.query(models.PlaybookVoce).one()
    assert voce.origine == "vademecum"
    assert voce.stato == "validata"
    assert float(voce.confidence) == pytest.approx(0.81)
    assert voce.origin_suggestion_id == suggestion.id
    assert voce.validata_da_user_id == actor.id
