"""Provider anthropic per l'estrazione avvisi (override per-agente)."""
import json
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from ai_agents.llm import call_ollama_json


def _fake_anthropic_module(returned_json: str):
    block = SimpleNamespace(type="text", text=returned_json)
    msg = SimpleNamespace(content=[block])
    client = MagicMock()
    client.messages.create.return_value = msg
    mod = MagicMock()
    mod.Anthropic.return_value = client
    return mod, client


def test_anthropic_override_ritorna_dict(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    mod, client = _fake_anthropic_module('{"regole": [], "scadenze": []}')
    with patch.dict("sys.modules", {"anthropic": mod}):
        out = call_ollama_json(
            system_prompt="estrai",
            user_prompt="testo avviso",
            provider="anthropic",
            model="claude-opus-4-8",
        )
    assert out == {"regole": [], "scadenze": []}
    # modello e system passati correttamente
    _, kwargs = client.messages.create.call_args
    assert kwargs["model"] == "claude-opus-4-8"
    assert "JSON" in kwargs["system"]


def test_anthropic_estrae_json_da_testo_con_prosa(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    mod, _ = _fake_anthropic_module('Ecco il risultato:\n```json\n{"regole":[{"chiave":"x"}]}\n```')
    with patch.dict("sys.modules", {"anthropic": mod}):
        out = call_ollama_json(system_prompt="s", user_prompt="u", provider="anthropic", model="claude-opus-4-8")
    assert out["regole"][0]["chiave"] == "x"


def test_anthropic_senza_key_errore(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    mod, _ = _fake_anthropic_module("{}")
    with patch.dict("sys.modules", {"anthropic": mod}):
        try:
            call_ollama_json(system_prompt="s", user_prompt="u", provider="anthropic")
            assert False, "atteso RuntimeError"
        except RuntimeError as e:
            assert "ANTHROPIC_API_KEY" in str(e)
