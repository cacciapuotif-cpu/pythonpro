from types import SimpleNamespace
import pytest
from ai_agents.llm_schemas import ProcedureEstrattoLLM
from ai_agents.procedure_extractor import collect_procedure_extractor_suggestions


class DB:
    def __init__(self, doc): self.doc = doc
    def get(self, _model, _id): return self.doc

class WriteFailDB(DB):
    def add(self, *_): raise AssertionError("collector non deve scrivere")
    def commit(self): raise AssertionError("collector non deve committare")
    def flush(self): raise AssertionError("collector non deve flushare")


def test_procedure_schema_drops_invalid_phase_and_clamps_confidence():
    result = ProcedureEstrattoLLM.model_validate({"voci":[
        {"fase":"avvio", "titolo":"OK", "testo_originale":"x", "confidence":4},
        {"fase":"inesistente", "titolo":"NO", "testo_originale":"x"},
    ]})
    assert len(result.voci) == 1 and result.voci[0].confidence == 1.0


def test_extractor_rejects_non_procedure_document():
    doc = SimpleNamespace(tipo="avviso", file_path="x.md")
    with pytest.raises(ValueError, match="vademecum|manuale"):
        collect_procedure_extractor_suggestions(DB(doc), documento_id=1)


def test_extractor_mocked_llm_returns_suggestions_without_writes(tmp_path, monkeypatch):
    from ai_agents import procedure_extractor as module
    source = tmp_path / "manuale.md"
    source.write_text("# Avvio\n\nControllare la convenzione.\n", encoding="utf-8")
    doc = SimpleNamespace(tipo="vademecum", file_path=str(source), id=4)
    monkeypatch.setattr(module, "call_ollama_json", lambda **_: {"voci":[
        {"fase":"avvio", "titolo":"Convenzione", "descrizione":"x",
         "tipo_contenuto":"attivita_semplice", "testo_originale":"Controllare", "confidence":0.8},
        {"fase":"bad", "titolo":"Scarta", "testo_originale":"x"},
    ]})
    result = collect_procedure_extractor_suggestions(WriteFailDB(doc), documento_id=4)
    assert len(result["suggestions"]) == 1
    assert result["suggestions"][0]["auto_fix_payload"]["kind"] == "playbook_voce"
    assert result["summary"]["gruppi_falliti"] == 0


def test_extractor_counts_failed_llm_group(tmp_path, monkeypatch):
    from ai_agents import procedure_extractor as module
    source = tmp_path / "manuale.md"; source.write_text("# X\n\nTesto\n", encoding="utf-8")
    doc = SimpleNamespace(tipo="manuale_gestione", file_path=str(source), id=5)
    monkeypatch.setattr(module, "call_ollama_json", lambda **_: (_ for _ in ()).throw(RuntimeError("timeout")))
    result = collect_procedure_extractor_suggestions(WriteFailDB(doc), documento_id=5)
    assert result["suggestions"] == [] and result["summary"]["gruppi_falliti"] == 1
