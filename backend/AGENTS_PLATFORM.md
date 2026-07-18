# Piattaforma Agenti — Guida

## Flusso canonico

```
trigger (manual | cron ARQ | event)
   → run_agent_workflow (agent_workflows.py)
      → AgentRun (persistente, trigger_mode nel payload)
      → runner del registry (collector puro, NESSUNA scrittura DB)
      → AgentSuggestion (+ AgentCommunicationDraft per le email)
   → revisione umana (UI /agents)
      → apply_workflow_action / apply_field_update_suggestion
      → AgentReviewAction + AuditLog
```

Regole non negoziabili:

- **Zero side effect senza approvazione umana**: nessun invio email/WhatsApp,
  nessuna scrittura anagrafica, nessuna validazione documento parte da un
  agente. Gli agenti producono solo proposte (suggestion + draft).
- **Ogni esecuzione passa da `run_agent_workflow`**: mai chiamare i collector
  direttamente da cron, router o altri servizi.
- **Kill switch**: `AGENTS_ENABLED` (globale) e `AGENT_<NOME>_ENABLED`
  (per agente) fermano ogni trigger (`ai_agents/control.py`).

## Registry unico (`ai_agents/__init__.py`)

Ogni agente e' una definizione dichiarativa in `_AGENT_DEFINITIONS`:

| Campo | Significato |
|-------|-------------|
| `name` | identificatore (= `agent_type` di AgentRun) |
| `description` | testo per dashboard |
| `supported_entity_types` | entity_type ammessi in `run_agent_workflow` |
| `triggers` | documentazione trigger: `manual`, `cron:...`, `event:...` |
| `kill_switch_env` | env var che disabilita l'agente |
| `allowed_roles` | ruoli che possono eseguirlo (enforcement al GATE A5a) |
| `version` | versione runner |
| `runner` | collector `(db, *, entity_type, entity_id, input_payload) -> {"summary", "suggestions"}` |

Il runner e' un **collector puro**: legge dal DB, NON scrive. Ogni item in
`suggestions` ha: `entity_type`, `entity_id`, `suggestion_type`, `severity`,
`title`, `description`, `payload` (dict), `confidence`.

Agenti registrati: `data_quality`, `mail_recovery`, `contract_agent`,
`certification`, `avviso_extractor`, `activity_planner`, `procedure_extractor`.
`activity_planner` è deterministico e propone un piano da scadenze/playbook
validati; `procedure_extractor` legge vademecum/manuali markdown e propone voci
playbook. Entrambi hanno trigger solo `manual`, kill switch per agente e ruoli
admin/manager. L'intake email (`email_intake`) crea AgentRun/Suggestion
dal worker inbox e non e' eseguibile manualmente.

## Aggiungere un agente (esempio minimale)

```python
# ai_agents/mio_agente.py
def collect_mio_agente_suggestions(db, *, entity_id=None):
    items = []
    for record in query_qualcosa(db, entity_id):
        items.append({
            "entity_type": "collaborator",
            "entity_id": record.id,
            "suggestion_type": "mio_check",
            "severity": "medium",
            "title": f"Check per {record.nome}",
            "description": "Cosa proporre e perche'.",
            "confidence": 0.9,
            "payload": {"campo": "valore"},
        })
    return {"summary": {"scansionati": len(items)}, "suggestions": items}
```

Poi in `ai_agents/__init__.py`: wrapper `_run_mio_agente(db, *, entity_type,
entity_id, input_payload)` + entry in `_AGENT_DEFINITIONS` con
`kill_switch_env=agent_env_name("mio_agente")`. Un test per il collector
(nessuna scrittura DB) e uno per il run via workflow.

Trigger cron: aggiungere in `arq_worker.py` una funzione che controlla
`agent_enabled("mio_agente")` e chiama
`run_agent_workflow(db, agent_type="mio_agente", auto_mode=True)`.

Il sottosistema A usa inoltre `attivita_piano` e `playbook_voce` come kind di
apply umano. La materializzazione passa dai servizi di dominio e richiede sempre
`user_id`; `AttivitaEvento` è append-only e costituisce il ponte verso il
sottosistema B. Nessun cron è previsto per questi due agenti nell'MVP.

## Storia

- Il registry legacy `ai_agents/registry.py` (BaseAgent/AgentRegistry, creava
  AgentRun internamente e non passava dal workflow) e' stato eliminato in
  AGENT-09/10 (ONDATA AGENTI A3). `jobs/run_agents.py` (scheduler CLI non
  referenziato) rimosso nella stessa ondata.
- Vincoli e storicizzazione: `REMEDIATION_LOG.md` sezioni "ONDATA AGENTI",
  piano in `docs/superpowers/plans/2026-07-14-ondata-agenti.md`.
