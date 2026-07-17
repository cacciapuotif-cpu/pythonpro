# PythonPro — Stato corrente

**Aggiornato:** 2026-07-17 19:07 Europe/Rome
**Branch:** `claude/platform-audit-compliance-XnH86` (locale, nessun push)
**Percorso:** `/DATA/progetti/pythonpro`

## Stato operativo

- Runtime: backend, frontend, PostgreSQL, Redis e ARQ worker healthy.
- Schema: Alembic `057` head; ultimo check documentato senza drift.
- Baseline backend più recente: **483 passed, 1 skipped, 0 failed**.
- V1 archivio avvisi e V2 pipeline ingestione sono chiuse.
- Wave dominio 1 e Wave 2.1 timesheet snapshot immutabile sono chiuse.
- Flusso agenti canonico attivo: collector puro → AgentRun/AgentSuggestion → approvazione umana → apply auditato. Nessun auto-apply.
- `AGENT_DATA_RETENTION_ENABLED=false` resta invariato.
- History Git contiene vecchi `.env`: **MAI push** finché non viene ripulita con procedura dedicata.

## Lavoro corrente — programma giro completo

Prompt operativo avviato il 2026-07-17. Sequenza richiesta:

1. Ondata S — fix rapidi sicurezza.
2. V5 — ingestione dei quattro avvisi reali.
3. Ondata B — binding avviso → operatività.
4. Ondata L — case base, FTS, advisor e feedback loop.
5. Ondata C — fondamenta GDPR; CRM solo dopo prerequisito legale esterno.
6. Ondata F — rifiniture e dimostrazione end-to-end.

L'utente ha autorizzato preventivamente i gate tecnici e ha chiesto di non fermarsi per approvazioni. Eccezione: C1 richiede evidenza esterna che informative e LIA siano state predisposte; C2 non può essere attivata inventando tale fatto.

## Ondata S — stato

- Memoria letta: `REMEDIATION_LOG.md`, precedente `STATUS.md`, `audit/FINDINGS_NUOVI.md`, `audit/ANALISI_ARCHITETTURA_2026-07-17.md`, ultimi 20 commit.
- Backup fresco verificato: `/app/backups/gestionale_backup_ondata_s_pre_20260717_162634.sql.zip.gpg` (`INTEGRITY=True`).
- Riorganizzazione stato: storico completo spostato in `STATUS_ARCHIVE_2026H1.md`; questo file resta sintetico e deve rimanere entro 200 righe.
- S1 chiuso: token random firmati, scadenza 24h, confronto constant-time e input malformati fail-closed (`41b6048`, `80d4b01`).
- S2 chiuso: snapshot `SecurityAuditLog` redatti e retention 24 mesi configurabile via proposta `data_retention`, apply solo umano (`c423669`). Kill switch invariato disattivo.
- S3 chiuso sul branch corrente: `.env.development` convertito in sample con placeholder; runtime pulito; backup env riemerso archiviato in `/DATA/progetti/pythonpro-local-archive/2026-07-17_ondata_s/` (`26ff969`). Residuo worktree separata = NEW-012.
- S4 chiuso: firma WhatsApp HMAC-SHA256 sul raw body, compare constant-time e input malformati fail-closed (`3683d48`).
- S5 al GATE: raccomandazione **SÌ, wire dopo hardening minimo**; nessuna implementazione eseguita in attesa di conferma.
- S6: non iniziato.

## Regole di lavoro

- Codice nuovo nei servizi di dominio; vietato aggiungere funzioni a `backend/crud.py` root.
- Commit atomici locali `feat/fix(ID): ...`; mai push.
- Ogni modifica con test; suite completa verde a fine punto/ondata.
- Migration esclusivamente Alembic, prima provata su copia DB con verifica dati e drift.
- Nuovi problemi in `audit/FINDINGS_NUOVI.md`.
- LLM e agenti propongono soltanto; applicazione sempre umana.
- Preservare modifiche preesistenti e usare staging selettivo.

## Ripresa immediata

1. Attendere conferma utente al GATE S5 sulla raccomandazione di rendere operativo il generatore rendicontazione dopo hardening anti-cross-company.
2. Dopo conferma: implementare S5 in `services/rendicontazione`, endpoint RBAC admin/operatore e test; poi S6 e gate Ondata S.
3. Proseguire automaticamente con V5 se i quattro file MD sono presenti; in loro assenza il prerequisito è oggettivamente bloccante.

## Memoria storica

- Storico precedente completo: `STATUS_ARCHIVE_2026H1.md`.
- Decisioni/verifiche dettagliate: `REMEDIATION_LOG.md`.
- Findings: `audit/FINDINGS_NUOVI.md`.
- Analisi guida: `audit/ANALISI_ARCHITETTURA_2026-07-17.md`.
