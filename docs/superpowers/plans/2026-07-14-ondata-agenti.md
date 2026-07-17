# ONDATA AGENTI — Piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (esecuzione inline in questa sessione). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendere la piattaforma agenti conforme al flusso canonico: trigger → AgentRun → AgentSuggestion → [Draft] → revisione umana → AgentReviewAction + audit → stato. Zero side effect esterni senza approvazione umana.

**Architettura:** FastAPI + SQLAlchemy (Base unica in `database.py`), workflow moderno in `agent_workflows.run_agent_workflow`, registry legacy in `ai_agents/registry.py`, scheduler ARQ in `arq_worker.py`, inbox IMAP in `services/email_inbox_worker.py`.

**Tech stack:** Python 3.11 container, pytest in container (`make test-container`), SQLite per test, Alembic per migrations.

## Vincoli globali

- Commit atomici `fix(AGENT-NN): descrizione`, MAI push.
- Ogni fix ha un test; suite completa sempre verde a fine punto.
- MAI invii reali email/WhatsApp nei test: mock SMTP/provider.
- Problemi nuovi → `audit/FINDINGS_NUOVI.md`.
- REMEDIATION_LOG.md aggiornato a ogni punto chiuso, sezione "ONDATA AGENTI".
- GATE su A3 (mappa migrazione registry) e A5a (matrice RBAC): attendere conferma utente.
- Il worktree contiene lavoro pre-esistente NON committato (censito in `audit/WORKTREE_PREESISTENTE.md`, pre-Ondata 1). Policy: hunk agentici conformi alla spec vengono verificati, testati e adottati nei commit atomici di quest'ondata (con nota nel log); hunk fuori scope restano non committati e non vengono toccati.
- Il codice backend è montato come volume nei container (`./backend:/app`): il worktree È il runtime. Attenzione a stati intermedi.

## Contesto verificato (fatti, non ipotesi)

1. **Auto-send mail_recovery**: pre-esistente nel worktree la forzatura `mail_recovery_decision = "draft"` (`agent_workflows.py:455`); restano rami morti `auto_send` (righe 476-477, 487, 508-545).
2. **Reply automatica inbox**: `EmailInboxWorker._process_single_message` invia reply via `InboxReplyComposer.send_reply` su documento invalido e su allegato non supportato (righe 160-166, 225-231).
3. **Auto-validazione LLM**: `DocumentProcessor._apply_confidence_decision` forza `valid=True` con confidence ≥ 0.85; `_parse_llm_result_dict` ha override `False→True` (righe 205-210, 251-258).
4. **Update anagrafici auto**: `DocumentIntakeAgent.apply_document_result` con `valid=True` setta `documento.stato="validato"` (validato_da="email_agent") e applica campi collaboratore; `_apply_company_document_result` applica campi azienda SENZA gate su `valid` (AI-01). `_apply_body_extracted_data` in email_inbox_worker applica P.IVA/CF/telefono dal body email.
5. **Kill switch**: `ai_agents/control.py` esiste (untracked, pre-esistente): `agents_enabled()`, `agent_enabled(name)`, `disabled_reason(name)`. Già cablato in `run_agent_workflow`, `sync_collaborator_data_quality`, `promote_due_followups`. NON cablato nei cron ARQ (`poll_email_inbox`, `run_mail_recovery_cron`, `run_contract_agent_cron`, `run_certification_agent_cron`, `data_retention_cleanup`) né in `trigger-poll` endpoint.
6. **A2a root cause**: `AgentReviewAction.reviewed_by_user_id` → FK `users.id`; `User` è dichiarato in `auth.py` (stessa `Base`); il processo ARQ importa solo `models` via `agent_workflows` → la tabella `users` non entra nella metadata → `NoReferencedTableError` alla flush.
7. **A2b bypass censiti**: `run_mail_recovery_cron` → `run_mail_recovery_agent` diretto; `run_contract_agent_cron` → `run_contract_agent`; `run_certification_agent_cron` → `run_certification_agent`; `routers/sprint7.py:84-95` → chiamate dirette; `jobs/run_agents.py` → `agent_registry.run_agent`; `DocumentIntakeAgent._trigger_contract_agent` → `run_contract_agent_for_collaborator`.
8. **apply-fix finto**: `POST /suggestions/{id}/apply-fix` NON applica nulla: crea review action e marca "implemented". Da censire in FINDINGS_NUOVI e sostituire con applicazione reale del diff proposto (A1b).
9. **Stato inbox cross-process**: `/email-inbox/status` legge `_WORKER_STATUS` in-process: il backend non vede lo stato del worker ARQ. Serve store condiviso (Redis con fallback in-memory; Redis in test è irraggiungibile per design).
10. **data_retention_cleanup** (pre-esistente, untracked in arq_worker): anonimizza collaboratori e invia email report automaticamente ogni domenica 03:00. Side effect non revisionato fuori spec agenti → finding nuovo + gate dietro kill switch globale.
11. **RBAC pre-esistente** su `routers/agents.py`: dipendenze `require_agents_execute/write` = ADMIN|MANAGER. Da riconciliare con matrice A5a (GATE) — nel frattempo si adotta perché più restrittivo di prima (endpoint erano aperti).
12. Suite di riferimento: `make test-container` (pytest dentro container backend, DB sqlite /tmp).

---

## PUNTO A1 — Automatismi pericolosi

### Task A1.1 — Kill switch completo sui trigger (AGENT-01)

**Files:**
- Modify: `backend/arq_worker.py` (gate su ogni cron)
- Adopt: `backend/ai_agents/control.py` (pre-esistente, invariato)
- Adopt hunks: `backend/agent_workflows.py` (gate già cablati)
- Test: `backend/tests/test_agent_kill_switch.py` (nuovo)

**Comportamento:**
- Ogni cron ARQ agentico esce subito con `{"status": "skipped", "reason": disabled_reason(...)}` se `agent_enabled(<nome>)` è false (o `agents_enabled()` per job trasversali: `promote_agent_followups`, `poll_email_inbox` usa `agent_enabled("email_intake")`, `data_retention_cleanup` usa `agents_enabled()`).
- `run_agent_workflow` già rifiuta con ValueError se disabilitato (manuale incluso). UI GET non toccata.

**Test (nomi):**
- `test_agents_enabled_default_true`
- `test_agent_env_name_normalization`
- `test_run_agent_workflow_blocked_when_disabled` (monkeypatch env AGENTS_ENABLED=false → ValueError, nessun AgentRun creato)
- `test_cron_functions_skip_when_disabled` (asyncio run dei cron con env false → status skipped, nessuna query)
- `test_sync_data_quality_skips_when_agent_disabled`

Commit: `fix(AGENT-01): kill switch globale e per-agente su tutti i trigger`

### Task A1.2 — Auto-send mail_recovery rimosso (AGENT-02)

**Files:**
- Modify: `backend/agent_workflows.py` — rimuovere ramo `auto_send` morto (476-477, 487, 508-545), contatore `auto_sent_emails`, decisione ridotta a draft/scarto.
- Test: `backend/tests/test_agent_no_autosend.py` (nuovo)

**Test:**
- `test_mail_recovery_high_confidence_creates_draft_not_send`: collaboratore con consenso, confidence 0.97 → suggestion status pending, draft status "draft", `_send_email` mockato MAI chiamato.
- `test_mail_recovery_summary_has_no_autosend`: summary contiene draft_emails, non auto_sent_emails.
- Grep di guardia nel test: `auto_send` assente da agent_workflows.

Commit: `fix(AGENT-02): eliminato percorso auto-send mail_recovery, solo bozze approvabili`

### Task A1.3 — Reply automatica inbox → draft approvabile (AGENT-03)

**Files:**
- Modify: `backend/services/email_inbox_worker.py` — sostituire `composer.send_reply(...)` (2 punti) con `_create_reply_draft(db, ...)`: crea AgentRun(email_intake) se non presente per l'item + AgentSuggestion(suggestion_type="inbox_reply_needed", status pending) + AgentCommunicationDraft(channel=email, status draft, subject/body da InboxReplyComposer template renderer separato dall'invio).
- Modify: `backend/services/inbox_reply_composer.py` — separare `compose(...) -> (subject, body)` da `send_reply` (che resta per il flusso approvato UI, se usato).
- Test: `backend/tests/test_inbox_reply_draft.py`

**Test:**
- `test_invalid_document_creates_reply_draft_no_send` (mock EmailSender: mai chiamato; draft esiste con recipient=sender)
- `test_unsupported_attachment_creates_reply_draft_no_send`
- `test_reply_draft_sent_only_via_workflow_action` (apply_workflow_action approve_email con _send_email mockato ok → draft sent)

Commit: `fix(AGENT-03): reply inbox non più automatica, diventa bozza da approvare`

### Task A1.4 — Auto-validazione e update anagrafici → proposta con diff (AGENT-04)

**Files:**
- Modify: `backend/ai_agents/document_processor.py` — `_apply_confidence_decision` non forza più `valid=True` (confidence ≥0.85 → resta classificazione con `valid` così com'è ma SENZA effetti); rimosso override False→True in `_parse_llm_result_dict`.
- Modify: `backend/services/document_intake_agent.py` — `apply_document_result` NON scrive più campi collaboratore/azienda e NON valida documenti: allega file a DocumentoRichiesto (stato "caricato"), calcola diff campo per campo (valore attuale → proposto, con confidence) e crea AgentSuggestion `document_field_updates` con `auto_fix_available=True`, `auto_fix_payload=diff JSON`. `_apply_company_document_result` idem (fix AI-01). Trigger contract_agent NON parte più da qui.
- Modify: `backend/services/email_inbox_worker.py` — `_apply_body_extracted_data` diventa proposta nello stesso diff (niente scrittura diretta); `_create_auto_update_suggestion` sostituita dalla suggestion con diff.
- Modify: `backend/routers/agents.py` + nuovo service `backend/services/agent_apply_service.py` — `apply-fix` applica DAVVERO il diff (whitelist campi per entity_type, valori attuali ricontrollati, audit log per campo, stato suggestion "implemented", review action con esito reale).
- Modify: `backend/routers/documenti_richiesti.py` — alla validazione umana del documento parte `_trigger_contract_agent` (spostato qui).
- Test: `backend/tests/test_document_intake_proposal.py`

**Test:**
- `test_llm_valid_result_does_not_touch_collaborator`
- `test_company_document_does_not_touch_azienda` (AI-01)
- `test_confidence_override_removed` (valid False + confidence 0.9 resta False; nessuna auto-validazione)
- `test_diff_payload_structure` (campo, current, proposed, confidence)
- `test_apply_fix_applies_diff_with_audit`
- `test_apply_fix_skips_stale_values` (valore attuale cambiato nel frattempo → campo saltato e segnalato)
- `test_document_stays_caricato_until_human_validation`
- `test_contract_trigger_on_human_validation_only`

Commit: `fix(AGENT-04): documenti e anagrafiche solo per proposta, apply-fix reale con audit`

### Task A1.5 — FINDINGS_NUOVI + log (AGENT-05)

- `audit/FINDINGS_NUOVI.md`: NEW-00x apply-fix finto; NEW-00x data_retention_cleanup side effect automatico; NEW-00x /email-inbox/status cross-process stantio.
- REMEDIATION_LOG.md sezione ONDATA AGENTI aggiornata con A1.

---

## PUNTO A2 — Rotture tecniche

### Task A2.1 — Metadata users nel worker ARQ (AGENT-06)
- Modify: `backend/arq_worker.py` — import `auth` (registra User nella Base metadata) con commento sul perché.
- Test `backend/tests/test_arq_worker_context.py`: subprocess `python -c "import arq_worker; from database import Base; assert 'users' in Base.metadata.tables"` + test funzionale `promote_due_followups` con draft sent >7gg → review action flushata senza NoReferencedTableError.

### Task A2.2 — Cron mail_recovery via workflow (AGENT-07)
- Modify: `backend/arq_worker.py` — `run_mail_recovery_cron` chiama `run_agent_workflow(db, agent_type="mail_recovery", auto_mode=True)`.
- Census bypass residui documentato nel log (contract/certification → migrazione in A3, GATE).
- Test: cron produce AgentRun persistente con trigger_mode automatic.

### Task A2.3 — IMAP resiliente (AGENT-08)
- Modify: `backend/services/email_inbox_worker.py` — classificare auth failure; stato condiviso (Redis via cache esistente, fallback in-memory: `services/inbox_status_store.py`): {state: connected|auth_failed|error|disabled, last_error, failed_attempts, next_retry_at, last_success_at}. Backoff esponenziale: base 5m, x2, cap 6h; `poll_email_inbox` salta finché now < next_retry_at; su login ok reset.
- Modify: `backend/routers/email_inbox.py` — `/status` legge store condiviso; nuovo `POST /api/v1/email-inbox/imap/test` (admin) tenta login e riporta esito senza credenziali.
- Test: `backend/tests/test_imap_resilience.py` (mock imaplib): backoff crescente, skip prima di next_retry, reset su successo, endpoint test non espone password, messaggio "Inbox: disconnessa — credenziali non valide".

---

## PUNTO A3 — Registry unico (GATE prima di eliminare legacy)

- Estendere `_AGENT_DEFINITIONS` → registry unico dichiarativo: name, description, supported_entity_types, triggers (cron/event/manual), kill_switch env, allowed_roles, runner.
- Migrare `contract_generator`(→`contract_agent`), `certification` come agenti workflow: i runner ritornano `{"summary", "suggestions"}`.
- Cron contract/certification → `run_agent_workflow`. Sprint7 endpoints → `run_agent_workflow`. `jobs/run_agents.py` → workflow o rimozione se non referenziato (verificare).
- `DocumentIntakeAgent._trigger_contract_agent` → `run_agent_workflow(agent_type="contract_agent", entity_id=collaboratore)`.
- Dashboard `/agents/` legge solo registry unico. `AGENTS_PLATFORM.md` in backend root con guida + esempio minimale.
- **GATE:** presentare mappa migrazione agente-per-agente prima di cancellare `registry.py` legacy.

## PUNTO A4 — Robustezza LLM

- `ai_agents/llm.py`: retry max 2 con backoff breve su timeout/5xx; validazione output con schema Pydantic (`MailCopySchema`, `DocumentResultSchema`); malformato → retry → fallback (mail: deterministico; documenti: manual_review, mai perso).
- Confidence bassa (<0.60) o campi incerti → suggestion priority "high"/flag `needs_careful_review` nel payload.
- Prompt → `backend/ai_agents/prompts/mail_recovery_v1.py` e `document_processor_v1.py` (o .md con header versione); `DocumentResult.prompt_version`; log strutturato per chiamata (agente, modello, durata, esito, token se presenti) senza contenuto documenti.
- Test: retry esaurito → fallback; output malformato → manual review; prompt_version registrata; log senza PII.

## PUNTO A5 — RBAC + UX (GATE matrice)

- a) Proposta matrice OPERATORE (review/approve/send/inbox) vs ADMIN (run manuale, config, kill switch, test IMAP). **GATE: attendere conferma.**
- b) Endpoint `/agents/system-health`: per agente ultimo run/esito/prossima schedulazione (da cron_jobs), stato IMAP (store A2.3), LLM health (probe esistente), coda ARQ (redis ping + queue depth). Frontend pannello in AgentsManager.
- c) Run failed con motivo sintetico in dashboard (già in AgentRun.error_message → esporre/filtrare in UI).

## PUNTO A6 — Test integrazione e2e

File `backend/tests/test_agents_e2e.py` con i 6 flussi della spec, mock SMTP (mock `smtplib.SMTP`), mock IMAP (fixture messaggi), mock LLM (monkeypatch `call_ollama_json`).

## GATE FINALE

- Suite completa verde; grep `run_.*_agent\(` fuori da workflow = zero; zero side effect non approvati dimostrato dai test A1; REMEDIATION_LOG completo; dichiarazione finale conformità SÌ/NO.
