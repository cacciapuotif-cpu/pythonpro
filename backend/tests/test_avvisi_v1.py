"""ONDATA ARCHIVIO AVVISI — modello dati e CRUD V1."""

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import auth
import crud_avvisi
import models
import schemas_avvisi as avvisi_schemas
from database import Base


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(
        "sqlite:///{}".format(tmp_path / "avvisi_v1.db"),
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
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def user(db_session):
    obj = auth.User(
        username="reviewer-avvisi",
        email="reviewer.avvisi@example.com",
        hashed_password="not-used",
        role="admin",
        is_active=True,
    )
    db_session.add(obj)
    db_session.commit()
    return obj


def make_avviso(db_session, *, numero="3", ente="Fondimpresa", fondo="fondimpresa"):
    return crud_avvisi.create_avviso(
        db_session,
        avvisi_schemas.AvvisoCreate(
            fondo=fondo,
            numero=numero,
            anno=2026,
            titolo=f"Avviso {numero}/2026",
            ente_erogatore=ente,
        ),
    )


def make_revision(db_session, avviso, user, *, checksum="a" * 64, label="rev. 1"):
    return crud_avvisi.create_next_revision(
        db_session,
        avviso.id,
        avvisi_schemas.AvvisoRevisioneCreate(
            titolo=avviso.titolo,
            etichetta_revisione=label,
            source_md_path=f"avvisi/{avviso.id}/{label.replace(' ', '_')}.md",
            original_filename="avviso.md",
            source_sha256=checksum,
            data_scadenza_presentazione=datetime(2026, 9, 30, 13, tzinfo=timezone.utc),
        ),
        created_by_user_id=user.id,
    )


def money_rule(*, suggestion_id=None, confidence="0.91"):
    return avvisi_schemas.AvvisoRegolaProposal(
        categoria="massimali",
        chiave="costo_orario_max_docente_fascia_a",
        valore={"tipo": "denaro", "importo": "165.00", "valuta": "EUR"},
        unita="EUR/ora",
        testo_originale="Il costo massimo ammissibile è pari a euro 165,00 per ora.",
        riferimento_articolo="Art. 7",
        confidence=Decimal(confidence),
        origin_suggestion_id=suggestion_id,
    )


def duration_rule():
    return avvisi_schemas.AvvisoRegolaProposal(
        categoria="attuazione",
        sottocategoria="attuazione",
        chiave="termine_conclusione_da_sottoscrizione",
        valore={
            "tipo": "durata_termine",
            "tipo_termine": "conclusione",
            "ancoraggio": "sottoscrizione",
            "durata": {"valore": 12, "unita": "mesi"},
            "prorogabile": True,
            "tassativo": True,
            "slittamento_giorno_non_lavorativo": "non_specificato",
        },
        testo_originale=(
            "Il piano formativo deve concludersi entro dodici mesi dalla data "
            "di sottoscrizione della convenzione."
        ),
        riferimento_articolo="Art. 8",
        confidence=Decimal("0.94"),
    )


def test_avviso_identity_unique_and_regional_discriminator(db_session):
    make_avviso(db_session)
    with pytest.raises(ValueError, match="stessa identità"):
        make_avviso(db_session)

    regional = make_avviso(
        db_session, numero="3", ente="Regione Lazio", fondo="regionale"
    )
    assert regional.id is not None


def test_revision_history_is_immutable_and_current_moves(db_session, user):
    avviso = make_avviso(db_session)
    first = make_revision(db_session, avviso, user)
    second = make_revision(
        db_session, avviso, user, checksum="b" * 64, label="rev. 2"
    )
    db_session.refresh(avviso)
    assert first.numero_revisione == 1
    assert second.numero_revisione == 2
    assert second.revisione_precedente_id == first.id
    assert avviso.revisione_corrente_id == second.id


def test_duplicate_revision_source_is_rejected(db_session, user):
    avviso = make_avviso(db_session)
    make_revision(db_session, avviso, user)
    with pytest.raises(ValueError, match="già presente"):
        make_revision(db_session, avviso, user, label="duplicate")


def test_rule_json_roundtrip_and_human_validation(db_session, user):
    avviso = make_avviso(db_session)
    revision = make_revision(db_session, avviso, user)
    rule = crud_avvisi.create_rule_proposal(db_session, revision.id, money_rule())
    assert rule.stato == "proposta"
    assert rule.valore == {"tipo": "denaro", "importo": "165.00", "valuta": "EUR"}
    assert crud_avvisi.get_validated_rules(db_session, avviso.id) == []

    reviewed = crud_avvisi.review_rule(
        db_session,
        rule.id,
        action="approva",
        reviewer_user_id=user.id,
        corrected_value={"tipo": "denaro", "importo": "160.00", "valuta": "EUR"},
        note="Allineato alla tabella ufficiale",
    )
    assert reviewed.stato == "validata"
    assert reviewed.validata_da_user_id == user.id
    assert reviewed.validata_il is not None
    assert crud_avvisi.get_validated_rules(db_session, avviso.id)[0].id == rule.id


def test_duration_rule_json_roundtrip_uses_versioned_metadata(db_session, user):
    avviso = make_avviso(db_session)
    revision = make_revision(db_session, avviso, user)

    rule = crud_avvisi.create_rule_proposal(db_session, revision.id, duration_rule())

    assert rule.valore == {
        "tipo": "durata_termine",
        "tipo_termine": "conclusione",
        "ancoraggio": "sottoscrizione",
        "durata": {"valore": 12, "unita": "mesi"},
        "prorogabile": True,
        "tassativo": True,
        "slittamento_giorno_non_lavorativo": "non_specificato",
    }
    assert rule.tipo_valore == "durata_termine"
    assert rule.schema_version == 2


def test_human_review_cannot_validate_malformed_duration_value(db_session, user):
    avviso = make_avviso(db_session)
    revision = make_revision(db_session, avviso, user)
    rule = crud_avvisi.create_rule_proposal(db_session, revision.id, duration_rule())

    malformed = dict(rule.valore)
    malformed["ancoraggio"] = "pubblicazione"
    with pytest.raises(ValidationError):
        crud_avvisi.review_rule(
            db_session,
            rule.id,
            action="approva",
            reviewer_user_id=user.id,
            corrected_value=malformed,
        )

    db_session.refresh(rule)
    assert rule.stato == "proposta"
    assert rule.valore["ancoraggio"] == "sottoscrizione"


def test_human_review_revalidates_persisted_json_before_approval(db_session, user):
    avviso = make_avviso(db_session)
    revision = make_revision(db_session, avviso, user)
    rule = crud_avvisi.create_rule_proposal(db_session, revision.id, duration_rule())
    malformed = dict(rule.valore)
    malformed["ancoraggio"] = "pubblicazione"
    rule.valore = malformed
    db_session.commit()

    with pytest.raises(ValidationError):
        crud_avvisi.review_rule(
            db_session,
            rule.id,
            action="approva",
            reviewer_user_id=user.id,
        )

    db_session.rollback()
    db_session.refresh(rule)
    assert rule.stato == "proposta"


@pytest.mark.parametrize(
    "changes",
    [
        {"riferimento_articolo": None},
        {"categoria": "massimali"},
        {"valore": {
            "tipo": "durata_termine",
            "tipo_termine": "conclusione",
            "ancoraggio": "pubblicazione",
            "durata": {"valore": 12, "unita": "mesi"},
            "prorogabile": True,
            "tassativo": True,
        }},
    ],
)
def test_duration_rule_rejects_missing_source_or_invalid_domain(changes):
    payload = duration_rule().model_dump(mode="python")
    payload.update(changes)

    with pytest.raises(ValidationError):
        avvisi_schemas.AvvisoRegolaProposal.model_validate(payload)


def test_existing_rule_value_shapes_remain_compatible():
    assert money_rule().valore.tipo == "denaro"


def test_new_revision_does_not_activate_previous_rules(db_session, user):
    avviso = make_avviso(db_session)
    first = make_revision(db_session, avviso, user)
    rule = crud_avvisi.create_rule_proposal(db_session, first.id, money_rule())
    crud_avvisi.review_rule(
        db_session, rule.id, action="approva", reviewer_user_id=user.id
    )
    second = make_revision(db_session, avviso, user, checksum="b" * 64, label="rev. 2")

    assert crud_avvisi.get_validated_rules(db_session, avviso.id) == []
    assert crud_avvisi.get_validated_rules(db_session, avviso.id, first.id)[0].stato == "validata"
    assert second.regole == []


def test_rule_schema_rejects_unknown_shape_and_bad_confidence():
    with pytest.raises(ValidationError):
        money_rule(confidence="1.01")
    with pytest.raises(ValidationError):
        avvisi_schemas.AvvisoRegolaProposal(
            categoria="massimali",
            chiave="massimale",
            valore={"tipo": "inventato", "valore": 10},
            testo_originale="Fonte",
        )


def test_deadline_is_inactive_until_human_review(db_session, user):
    avviso = make_avviso(db_session)
    revision = make_revision(db_session, avviso, user)
    proposal = avvisi_schemas.AvvisoScadenzaProposal(
        tipo="presentazione",
        data=datetime(2026, 9, 30, 13, tzinfo=timezone.utc),
        descrizione="Termine presentazione",
        tassativa=True,
        testo_originale="Le domande devono pervenire entro le ore 15:00 del 30 settembre.",
        confidence=Decimal("0.88"),
    )
    deadline = crud_avvisi.create_deadline_proposal(db_session, revision.id, proposal)
    assert deadline.stato == "proposta"
    reviewed = crud_avvisi.review_deadline(
        db_session, deadline.id, action="approva", reviewer_user_id=user.id
    )
    assert reviewed.stato == "validata"
    assert reviewed.validata_da_user_id == user.id


def test_source_storage_keys_cannot_escape_ingest_root(db_session, user):
    avviso = make_avviso(db_session)
    payload = avvisi_schemas.AvvisoRevisioneCreate(
        titolo="Unsafe",
        source_md_path="../../etc/passwd",
        original_filename="avviso.md",
        source_sha256="c" * 64,
    )
    with pytest.raises(ValueError, match="Storage key"):
        crud_avvisi.create_next_revision(
            db_session, avviso.id, payload, created_by_user_id=user.id
        )


def test_document_and_knowledge_require_revision_ownership(db_session, user):
    first = make_avviso(db_session)
    second = make_avviso(db_session, numero="4")
    revision = make_revision(db_session, first, user)
    document_payload = avvisi_schemas.AvvisoDocumentoCreate(
        avviso_revisione_id=revision.id,
        tipo="allegato",
        original_filename="allegato.md",
        file_path="avvisi/allegato.md",
        mime_type="text/markdown",
        sha256="d" * 64,
    )
    with pytest.raises(ValueError, match="non appartiene"):
        crud_avvisi.create_document(
            db_session, second.id, document_payload, uploaded_by_user_id=user.id
        )
    knowledge = crud_avvisi.create_knowledge(
        db_session,
        first.id,
        avvisi_schemas.AvvisoConoscenzaCreate(
            avviso_revisione_id=revision.id,
            tipo="errore_da_evitare",
            contenuto="Verificare sempre le note alle tabelle.",
            tags=["Tabelle", "tabelle", " Rendicontazione "],
        ),
        author_user_id=user.id,
    )
    assert knowledge.tags == ["rendicontazione", "tabelle"]


def test_project_and_outcome_freeze_exact_revision(db_session, user):
    avviso = make_avviso(db_session)
    revision = make_revision(db_session, avviso, user)
    project = models.Project(
        name="Progetto Archivio",
        status="active",
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 12, 31),
        avviso_id=avviso.id,
        avviso_revisione_id=revision.id,
    )
    db_session.add(project)
    db_session.commit()
    outcome = crud_avvisi.create_project_outcome(
        db_session,
        avviso.id,
        avvisi_schemas.AvvisoEsitoProgettoCreate(
            avviso_revisione_id=revision.id,
            project_id=project.id,
            esito="approvato",
            data_evento=datetime(2026, 5, 2, tzinfo=timezone.utc),
            importo_richiesto=Decimal("100000.00"),
            importo_ammesso=Decimal("95000.00"),
        ),
        created_by_user_id=user.id,
    )
    assert outcome.avviso_revisione_id == revision.id
    assert outcome.importo_ammesso == Decimal("95000.00")


def test_relation_to_financial_plans_uses_real_fk_not_legacy(db_session):
    avviso = make_avviso(db_session)
    project = models.Project(
        name="Piano link",
        status="active",
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 12, 31),
        avviso_id=avviso.id,
    )
    db_session.add(project)
    db_session.flush()
    plan = models.PianoFinanziario(
        progetto_id=project.id,
        anno=2026,
        nome="Piano",
        tipo_fondo="fondimpresa",
        avviso_pf_id=avviso.id,
        budget_totale=Decimal("1000"),
        data_inizio=datetime(2026, 1, 1),
        data_fine=datetime(2026, 12, 31),
    )
    db_session.add(plan)
    db_session.commit()
    db_session.expire(avviso, ["piani_finanziari"])
    assert [item.id for item in avviso.piani_finanziari] == [plan.id]
