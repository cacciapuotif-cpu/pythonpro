"""ONDATA ARCHIVIO AVVISI — V2: schemi LLM, collector avviso_extractor, pipeline, apply."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_agents.llm_schemas import AvvisoEstrazioneLLM
from ai_agents.prompts.avviso_extractor_v1 import (
    GRUPPI_CATEGORIE,
    SYSTEM_PROMPT_ESTRAZIONE,
    build_extraction_prompt,
)


def test_estrazione_schema_clamps_confidence_and_drops_invalid_items():
    parsed = AvvisoEstrazioneLLM.model_validate({
        "regole": [
            {
                "chiave": "contributo_massimo",
                "valore": {"tipo": "denaro", "importo": "50000", "valuta": "EUR"},
                "testo_originale": "Il contributo massimo è 50.000 euro",
                "confidence": 1.7,
            },
            {"senza_campi_obbligatori": True},
        ],
        "scadenze": [
            {
                "tipo": "tipologia_ignota",
                "data": "2026-09-30",
                "descrizione": "Termine presentazione",
                "testo_originale": "entro il 30/09/2026",
                "confidence": -3,
            }
        ],
    })
    assert len(parsed.regole) == 1
    assert parsed.regole[0].confidence == 1.0
    assert len(parsed.scadenze) == 1
    assert parsed.scadenze[0].tipo == "altro"
    assert parsed.scadenze[0].confidence == 0.0


def test_gruppi_categorie_cover_expected_categories():
    flat = [c for cats in GRUPPI_CATEGORIE.values() for c in cats]
    assert "massimali" in flat and "rendicontazione" in flat
    assert GRUPPI_CATEGORIE["scadenze"] == []


def test_build_extraction_prompt_mentions_categories_and_text():
    prompt = build_extraction_prompt("economiche", ["massimali", "parametri_costo"], "# Art. 5\nMassimale 50k")
    assert "massimali" in prompt and "parametri_costo" in prompt
    assert "Massimale 50k" in prompt
    assert "JSON" in SYSTEM_PROMPT_ESTRAZIONE


import hashlib
import json

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import models
import auth
import crud_avvisi
import schemas_avvisi as avvisi_schemas
from database import Base

from ai_agents import get_agent_definition
from ai_agents import avviso_extractor as extractor_module
from services import avviso_ingest


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(
        "sqlite:///{}".format(tmp_path / "avvisi_v2.db"),
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def user(db_session):
    record = auth.User(
        username="revisore",
        email="revisore@example.com",
        hashed_password="not-used",
        role="admin",
        is_active=True,
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


@pytest.fixture
def revision_with_cleaned_md(db_session, user, tmp_path, monkeypatch):
    monkeypatch.setattr(avviso_ingest, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(extractor_module, "UPLOAD_DIR", tmp_path)
    avviso = models.Avviso(
        codice="1/2026", ente_erogatore="fapi", fondo="fapi", numero="1", anno=2026,
        titolo="Avviso FAPI 1/2026", stato="bozza",
    )
    db_session.add(avviso)
    db_session.commit()
    contents = "# Art. 5 Massimali\nContributo massimo 50.000 euro.\n".encode("utf-8")
    sha = hashlib.sha256(contents).hexdigest()
    stored = avviso_ingest.save_ingest_markdown(avviso.id, "avviso.md", contents)
    cleaned = avviso_ingest.save_cleaned_markdown(avviso.id, sha, contents.decode("utf-8"))
    revision = crud_avvisi.create_next_revision(
        db_session,
        avviso.id,
        avvisi_schemas.AvvisoRevisioneCreate(
            titolo="Avviso FAPI 1/2026",
            source_md_path=stored.storage_key,
            cleaned_md_path=cleaned.storage_key,
            original_filename="avviso.md",
            source_sha256=sha,
        ),
        created_by_user_id=user.id,
    )
    return revision


def _fake_llm_factory(calls):
    def fake_call_ollama_json(*, system_prompt, user_prompt):
        calls.append(user_prompt)
        if "scadenze" in user_prompt.split("TESTO AVVISO:")[0]:
            return {
                "scadenze": [{
                    "tipo": "presentazione",
                    "data": "2026-09-30",
                    "descrizione": "Termine presentazione piani",
                    "tassativa": True,
                    "testo_originale": "entro il 30/09/2026",
                    "confidence": 0.9,
                }]
            }
        if "massimali" in user_prompt:
            return {
                "regole": [{
                    "chiave": "contributo_massimo",
                    "valore": {"tipo": "denaro", "importo": "50000", "valuta": "EUR"},
                    "testo_originale": "Contributo massimo 50.000 euro.",
                    "riferimento_articolo": "Art. 5",
                    "confidence": 0.9,
                }]
            }
        return {"regole": []}
    return fake_call_ollama_json


def test_registry_exposes_avviso_extractor():
    definition = get_agent_definition("avviso_extractor")
    assert definition is not None
    assert definition["supported_entity_types"] == ["avviso_revisione"]
    assert definition["kill_switch_env"] == "AGENT_AVVISO_EXTRACTOR_ENABLED"
    assert "runner" not in definition


def test_collector_builds_suggestions_from_llm(db_session, revision_with_cleaned_md, monkeypatch):
    calls = []
    monkeypatch.setattr(extractor_module, "call_ollama_json", _fake_llm_factory(calls))
    result = extractor_module.collect_avviso_extraction_suggestions(
        db_session, entity_type="avviso_revisione", entity_id=revision_with_cleaned_md.id,
    )
    assert len(calls) == 5  # 4 gruppi regole + 1 scadenze
    tipi = {s["suggestion_type"] for s in result["suggestions"]}
    assert tipi == {"avviso_regola_proposta", "avviso_scadenza_proposta"}
    regola = next(s for s in result["suggestions"] if s["suggestion_type"] == "avviso_regola_proposta")
    fix = regola["auto_fix_payload"]
    assert fix["kind"] == "avviso_estrazione"
    assert fix["target"] == "regola"
    assert fix["revision_id"] == revision_with_cleaned_md.id
    proposal = avvisi_schemas.AvvisoRegolaProposal.model_validate(fix["proposal"])
    assert proposal.categoria == "massimali"
    assert proposal.needs_careful_review is False
    scadenza = next(s for s in result["suggestions"] if s["suggestion_type"] == "avviso_scadenza_proposta")
    sc_proposal = avvisi_schemas.AvvisoScadenzaProposal.model_validate(scadenza["auto_fix_payload"]["proposal"])
    assert sc_proposal.data.tzinfo is not None


def test_collector_marks_invalid_rule_value_for_careful_review(db_session, revision_with_cleaned_md, monkeypatch):
    def bad_llm(*, system_prompt, user_prompt):
        if "massimali" in user_prompt:
            return {"regole": [{
                "chiave": "contributo_massimo",
                "valore": {"tipo": "inesistente", "x": 1},
                "testo_originale": "Contributo massimo 50.000 euro.",
                "confidence": 0.9,
            }]}
        return {"regole": [], "scadenze": []}
    monkeypatch.setattr(extractor_module, "call_ollama_json", bad_llm)
    result = extractor_module.collect_avviso_extraction_suggestions(
        db_session, entity_type="avviso_revisione", entity_id=revision_with_cleaned_md.id,
    )
    regola = next(s for s in result["suggestions"] if s["suggestion_type"] == "avviso_regola_proposta")
    proposal = regola["auto_fix_payload"]["proposal"]
    assert proposal["needs_careful_review"] is True
    assert proposal["valore"]["tipo"] == "testo"


def test_collector_tolerates_llm_failure_per_group(db_session, revision_with_cleaned_md, monkeypatch):
    def flaky(*, system_prompt, user_prompt):
        raise RuntimeError("LLM down")
    monkeypatch.setattr(extractor_module, "call_ollama_json", flaky)
    result = extractor_module.collect_avviso_extraction_suggestions(
        db_session, entity_type="avviso_revisione", entity_id=revision_with_cleaned_md.id,
    )
    assert result["suggestions"] == []
    assert result["summary"]["gruppi_falliti"] == 5


import agent_workflows
from services.avviso_ingest import prepare_revision_content, run_extraction_pipeline


@pytest.fixture
def revision_caricata(db_session, user, tmp_path, monkeypatch):
    """Revisione con solo source_md_path (stato caricato), senza cleaned."""
    monkeypatch.setattr(avviso_ingest, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(extractor_module, "UPLOAD_DIR", tmp_path)
    avviso = models.Avviso(
        codice="2/2026", ente_erogatore="fapi", fondo="fapi", numero="2", anno=2026,
        titolo="Avviso FAPI 2/2026", stato="bozza",
    )
    db_session.add(avviso)
    db_session.commit()
    contents = "# Art. 5 Massimali\r\n\r\n\r\nContributo massimo 50.000 euro.\n".encode("utf-8")
    stored = avviso_ingest.save_ingest_markdown(avviso.id, "avviso.md", contents)
    revision = crud_avvisi.create_next_revision(
        db_session,
        avviso.id,
        avvisi_schemas.AvvisoRevisioneCreate(
            titolo="Avviso FAPI 2/2026",
            source_md_path=stored.storage_key,
            original_filename="avviso.md",
            source_sha256=stored.sha256,
        ),
        created_by_user_id=user.id,
    )
    assert revision.stato_estrazione == "caricato"
    return revision


def test_prepare_revision_content_transitions_and_writes_cleaned(db_session, revision_caricata):
    revision = prepare_revision_content(db_session, revision_caricata.id)
    assert revision.stato_estrazione == "segmentato"
    assert revision.cleaned_md_path
    cleaned_text = (avviso_ingest.UPLOAD_DIR / revision.cleaned_md_path).read_text(encoding="utf-8")
    assert "\r" not in cleaned_text and "\n\n\n" not in cleaned_text


def test_run_extraction_pipeline_completes_and_links_run(db_session, revision_caricata, monkeypatch):
    monkeypatch.setattr(extractor_module, "call_ollama_json", _fake_llm_factory([]))
    run = run_extraction_pipeline(db_session, revision_caricata.id, user_id=None)
    db_session.refresh(revision_caricata)
    assert run.status == "completed"
    assert revision_caricata.extraction_run_id == run.id
    assert revision_caricata.stato_estrazione == "estratto"
    assert run.suggestions_count >= 2  # regola massimali + scadenza


def test_run_extraction_pipeline_marks_errore_on_workflow_failure(db_session, revision_caricata, monkeypatch):
    def boom(db, **kwargs):
        raise ValueError("Agente non supportato")
    monkeypatch.setattr(avviso_ingest, "run_agent_workflow", boom)
    with pytest.raises(ValueError):
        run_extraction_pipeline(db_session, revision_caricata.id, user_id=None)
    db_session.refresh(revision_caricata)
    assert revision_caricata.stato_estrazione == "errore"
