from pathlib import Path
import sys
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))
import auth
import models
from database import Base
from services.playbook import (add_voce_manuale, create_next_version, create_playbook,
                               get_playbook_operativo, review_voce)


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'playbook.db'}")
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    # Solo tabelle necessarie: nessun accoppiamento alla metadata legacy completa.
    for table in (models.Collaborator.__table__, auth.User.__table__, models.AgentRun.__table__, models.AgentSuggestion.__table__, models.Playbook.__table__, models.PlaybookVersione.__table__, models.PlaybookVoce.__table__):
        table.create(engine, checkfirst=True)
    session = sessionmaker(bind=engine)()
    yield session
    session.close(); engine.dispose()


def make_user(db, role="admin"):
    user = auth.User(username=f"{role}-x", email=f"{role}-x@example.test", hashed_password="x", role=role)
    db.add(user); db.commit(); return user


def test_versioning_carries_only_validated_voices(db):
    user = make_user(db)
    playbook = create_playbook(db, nome="FAPI", fondo="fapi", created_by_user_id=user.id)
    add_voce_manuale(db, versione_id=playbook.versione_corrente_id, fase="avvio", titolo="Validata",
                     contenuto={"tipo":"attivita_semplice"}, created_by_user_id=user.id)
    proposed = models.PlaybookVoce(playbook_versione_id=playbook.versione_corrente_id, fase="gestione",
                                    titolo="Proposta", contenuto={"tipo":"attivita_semplice"})
    db.add(proposed); db.commit()
    version = create_next_version(db, playbook_id=playbook.id, created_by_user_id=user.id)
    assert version.numero_versione == 2
    assert [v.titolo for v in version.voci] == ["Validata"]


def test_review_requires_proposal_and_reviewer(db):
    user = make_user(db)
    playbook = create_playbook(db, nome="P", fondo="fapi", created_by_user_id=user.id)
    voce = models.PlaybookVoce(playbook_versione_id=playbook.versione_corrente_id, fase="avvio",
                               titolo="Da validare", contenuto={"tipo":"attivita_semplice"})
    db.add(voce); db.commit()
    with pytest.raises(ValueError, match="Reviewer"):
        review_voce(db, voce_id=voce.id, azione="valida", reviewer_user_id=None)
    review_voce(db, voce_id=voce.id, azione="valida", reviewer_user_id=user.id)
    assert db.get(models.PlaybookVoce, voce.id).stato == "validata"


def test_operativo_prefers_entity_then_fondo_fallback(db):
    user = make_user(db)
    generic = create_playbook(db, nome="Generico", fondo="fapi", created_by_user_id=user.id)
    add_voce_manuale(db, versione_id=generic.versione_corrente_id, fase="gestione", titolo="Base",
                     contenuto={"tipo":"attivita_semplice"}, created_by_user_id=user.id)
    assert [v.titolo for v in get_playbook_operativo(db, fondo="fapi", ente_erogatore="INPS")] == ["Base"]
