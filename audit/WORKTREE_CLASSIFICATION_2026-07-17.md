# Classificazione worktree residuo — 2026-07-17

## Gruppi applicativi committabili separatamente

1. **DOM-04 — rimozione veto cross-ente**
   - `backend/crud.py`
   - `backend/tests/test_dom04_multiprogetto.py`
   - Effetto: consente assegnazioni sovrapposte anche tra enti; resta il vincolo orario sulle presenze.

2. **Sicurezza autenticazione e middleware**
   - `backend/request_middleware.py`
   - `backend/routers/auth.py`
   - parti pertinenti di `backend/tests/test_agent_audit_fixes.py`
   - Effetto: audit login/logout/refresh, revoca token, rate limit per endpoint, header CSP/HSTS.

3. **Sicurezza WhatsApp**
   - `backend/routers/whatsapp.py`
   - `backend/services/whatsapp_sender.py`
   - `backend/services/whatsapp_webhook_service.py`
   - `backend/tests/test_whatsapp_meta.py`
   - Effetto: firma webhook obbligatoria, confronto constant-time, URL provider HTTPS/no IP privati, minimizzazione log.

4. **Sicurezza upload e allegati**
   - `backend/file_upload.py`
   - `backend/services/attachment_handler.py`
   - Effetto: storage configurabile, magic-byte validation, timestamp UTC, protezione path traversal già presente.

5. **Frontend import Excel**
   - `frontend/src/utils/excelUtils.js`
   - i tre componenti `*BulkImport.js`
   - Effetto: sostituzione uso diretto `xlsx` con helper `exceljs` condiviso.

6. **Runtime hardening e stato inbox**
   - `docker-compose.yml`
   - `frontend/Dockerfile`
   - `frontend/nginx.conf`
   - `backend/services/email_inbox_worker.py`
   - `backend/services/inbox_status_store.py`
   - Effetto: servizi interni non esposti, frontend non-root su 8080, kill switch agenti espliciti, backup separato, stato inbox coerente.

## Documentazione storica

- `audit/FASE_*`, `audit/AUDIT_REPORT.md`, `audit/DOMINIO_FINANZIARIO_*`, `audit/WORKTREE_PREESISTENTE.md`
- `docs/superpowers/plans/2026-07-14-ondata-agenti.md`
- Possono essere raccolti in uno o più commit `docs(...)`; non influiscono sul runtime.

## Artefatti locali — non committare

- `# Premi Invio 3 volte per accettare defaults senza passphrase` e `.pub`: materiale chiave creato accidentalmente nella root.
- `*.bak_*`: copie locali di configurazioni e sorgenti.
- `.env.bak_*`: contengono potenzialmente segreti; restano esclusi da Git.
- `docker-entrypoint-initdb.d/010_create_app_user.sh`: script sperimentale non collegato al compose corrente (`DB_APP_USER/DB_APP_PASSWORD` non configurati); non committare senza un gate architetturale sui ruoli DB.

## File di stato

- `STATUS.md`, `REMEDIATION_LOG.md`, `audit/FINDINGS_NUOVI.md`: modifiche documentali correnti; committabili separatamente dopo la chiusura dei gruppi applicativi.
