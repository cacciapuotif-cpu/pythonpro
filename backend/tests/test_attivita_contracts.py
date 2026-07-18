"""Contratti invarianti del sottosistema A, indipendenti dal DB legacy."""
import pytest
from pydantic import TypeAdapter

from schemas_attivita import (
    AttivitaSemplice, DocumentoContenuto, ScadenzaRelativa, VoceContenuto,
)
from services.attivita import ATTIVITA_STATE_TRANSITIONS

CONTENUTO = TypeAdapter(VoceContenuto)


@pytest.mark.parametrize("payload, expected", [
    ({"tipo": "attivita_semplice"}, AttivitaSemplice),
    ({"tipo": "scadenza_relativa", "ancora": "avvio", "offset_giorni": -10}, ScadenzaRelativa),
    ({"tipo": "documento", "tipo_documento": "DURC"}, DocumentoContenuto),
])
def test_voce_contenuto_union_is_discriminated(payload, expected):
    value = CONTENUTO.validate_python(payload)
    assert isinstance(value, expected)


def test_voce_contenuto_rejects_unknown_variant():
    with pytest.raises(Exception):
        CONTENUTO.validate_python({"tipo": "inventato"})


def test_state_machine_is_explicit_and_has_no_implicit_edges():
    assert ATTIVITA_STATE_TRANSITIONS["da_fare"] == {"in_corso", "completata", "non_applicabile"}
    assert ATTIVITA_STATE_TRANSITIONS["completata"] == {"da_fare"}
    assert "in_corso" not in ATTIVITA_STATE_TRANSITIONS["completata"]
