import sys
import types

arq_module = types.ModuleType("arq")
arq_connections = types.ModuleType("arq.connections")
arq_connections.RedisSettings = object
arq_connections.create_pool = lambda *args, **kwargs: None
arq_module.connections = arq_connections
sys.modules.setdefault("arq", arq_module)
sys.modules.setdefault("arq.connections", arq_connections)

from ai_agents.data_quality import is_valid_codice_fiscale
from services.llm_privacy import pseudonymize_prompt


def test_codice_fiscale_valid_with_control_char():
    assert is_valid_codice_fiscale("RSSMRA80A01H501U") is True


def test_codice_fiscale_rejects_partita_iva():
    assert is_valid_codice_fiscale("12345678901") is False


def test_codice_fiscale_rejects_bad_control_char():
    assert is_valid_codice_fiscale("RSSMRA80A01H501A") is False


# I test di validate_sezioni_percentuali sono stati rimossi con la regola
# stessa: A>=70/C<=20/D<=10 apparteneva a uno schema macrovoci di altro fondo
# ed era inconciliabile col template Formazienda (DOM-05, GATE W1.2).
# Vedi tests/test_dom05_regole_percentuali.py.


def test_llm_privacy_pseudonymizes_pii_and_restores():
    result = pseudonymize_prompt("Mario Rossi CF RSSMRA80A01H501U email mario.rossi@example.com tel +39 3331234567")
    assert "[CF_1]" in result.text
    assert "[EMAIL_1]" in result.text
    assert "[TEL_1]" in result.text
    assert "RSSMRA80A01H501U" not in result.text
    assert result.restore(result.text)
