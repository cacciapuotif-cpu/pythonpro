"""FASE E1 (seed) — parità dei template seed con le costanti reali.

Copre (Task E1.1 Step 3 del piano 2026-07-19-ui-completamento):
- ``seed_templates`` crea N>0 template al primo giro e 0 al secondo (idempotenza);
- PARITÀ: per ogni fondo la ``struttura_voci`` del template seedato coincide con
  la derivazione programmatica dalle costanti reali ``VOICE_TEMPLATES`` e
  ``MACROVOCE_LIMITS_BY_FONDO`` (via ``get_macrovoce_limits``) importate da
  ``piano_finanziario_config`` — nessun valore hardcodato nel confronto;
- i template seedati sono attivi e versione=1.

La categoria di ogni voce è derivata con ``crud._derive_categoria_from_role``
(stessa euristica usata in produzione per le assignment): il test la riusa
per il confronto programmatico, così la parità resta vera anche se le
costanti evolvono.
"""

from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from crud import _derive_categoria_from_role
from database import Base
from piano_finanziario_config import VOICE_TEMPLATES, get_macrovoce_limits
from services.piano_templates import TEMPLATE_SEED, seed_templates


@pytest.fixture(scope="function")
def db_session(tmp_path):
    engine = create_engine(
        "sqlite:///{}".format(tmp_path / "piano_templates_seed.db"),
        connect_args={"check_same_thread": False},
    )
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _expected_struttura_voci(tipo_fondo: str) -> dict:
    """Derivazione attesa dalla SOLE costanti importate (nessun hardcode)."""
    return {
        "voci": [
            {
                "voce_codice": tpl["voce_codice"],
                "macrovoce": tpl["macrovoce"],
                "categoria": _derive_categoria_from_role(tpl["descrizione"]),
                "descrizione": tpl["descrizione"],
                "is_dynamic": tpl["is_dynamic"],
            }
            for tpl in VOICE_TEMPLATES
        ],
        "limiti_macrovoce": get_macrovoce_limits(tipo_fondo),
    }


def test_seed_crea_template_poi_idempotente(db_session):
    n1 = seed_templates(db_session)
    assert n1 > 0
    assert n1 == len(TEMPLATE_SEED)
    assert db_session.query(models.PianoFinanziarioTemplate).count() == n1

    n2 = seed_templates(db_session)
    assert n2 == 0
    assert db_session.query(models.PianoFinanziarioTemplate).count() == n1


def test_parita_struttura_voci_con_costanti(db_session):
    seed_templates(db_session)
    db_session.expire_all()

    templates = db_session.query(models.PianoFinanziarioTemplate).all()
    # Un template per ciascun fondo dichiarato nel seed (piano E1.1: i tre
    # fondi presenti nel DB reale), senza duplicati.
    assert {t.tipo_fondo for t in templates} == {s["tipo_fondo"] for s in TEMPLATE_SEED}
    assert {t.tipo_fondo for t in templates} == {"formazienda", "fapi", "fondimpresa"}
    assert len(templates) == len({t.tipo_fondo for t in templates})

    for template in templates:
        assert template.struttura_voci == _expected_struttura_voci(template.tipo_fondo)
        # Le voci coprono TUTTE le voci delle costanti, nell'ordine originale.
        assert [v["voce_codice"] for v in template.struttura_voci["voci"]] == [
            t["voce_codice"] for t in VOICE_TEMPLATES
        ]


def test_template_seed_attivi_e_versione_1(db_session):
    seed_templates(db_session)
    for template in db_session.query(models.PianoFinanziarioTemplate).all():
        assert template.is_active is True
        assert template.versione == 1
        assert template.nome
        assert template.descrizione
