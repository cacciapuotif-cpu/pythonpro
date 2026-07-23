# PythonPro — Stato corrente

**Aggiornato:** 2026-07-21 (fasi E2/E1/E3 chiuse, GATE E1 confermato; prossimo: GATE UI v3)
**Branch:** `claude/platform-audit-compliance-XnH86` (locale, nessun push)
**Percorso:** `/DATA/progetti/pythonpro`

## Stato operativo

- Runtime: backend, frontend, PostgreSQL, Redis e ARQ worker healthy.
- Schema reale: Alembic **`062` head** (template piani 060 + FTS archivio 061 +
  drop relitto legacy_template_id 062). Backend riavviato dopo 062 per
  riallineare il modello allo schema (il drop colonna dava 500 sui piani finché
  il processo caricava il vecchio modello).
- Baseline backend: **750 passed, 6 skipped, 0 failed**.
- Baseline frontend: **148 passed, 3 snapshot, 0 failed**; build production verde.
- Frontend ridispiegato il 2026-07-23 (bundle `main.018feb71.js`) con NEW-020 +
  UI-12: live allineato al codice committato.
- **RUNTIME ATTIVATO il 2026-07-21**: backend riavviato (carica NEW-030/037,
  rotte `/api/v1/archivio/*` live in openapi); frontend **ricostruito e
  ridispiegato** (`docker compose build frontend` + recreate, bundle
  `main.2f02630a.js` con pagina "Chiedi all'archivio"). Verifica live HTTP sul
  runtime: 3 ruoli → search/chiedi/projects 200; `/archivio-chiedi` servita 200;
  openapi espone `azienda_ids`/`allievo_ids` (NEW-030). Backend LAN-portabile:
  da `192.168.2.41:3001` il bundle punta a `192.168.2.41:8001` (http.js).
  Crawl Playwright browser-level NON eseguito: chromium headless privo di
  librerie di sistema (`libatk-1.0.so.0`) in questo ambiente — verifica ridotta
  a HTTP live + suite + jest (nessun render/console-error capturato).
- V1 archivio avvisi e V2 pipeline ingestione sono chiuse.
- Wave dominio 1 e Wave 2.1 timesheet snapshot immutabile sono chiuse.
- Flusso agenti canonico attivo: collector puro → AgentRun/AgentSuggestion → approvazione umana → apply auditato. Nessun auto-apply.
- `AGENT_DATA_RETENTION_ENABLED=false` resta invariato.
- History Git contiene vecchi `.env`: **MAI push** finché non viene ripulita con procedura dedicata.

## Ondata UI-COMPLETAMENTO — CHIUSA, GATE UI v3 SUPERATO (2026-07-21)

Chiuse le 3 eccezioni del GATE UI v2 (piano da template, E2E contratto, Chiedi
all'archivio) con ordine E2 → E1 → E3 → GATE v3. Metodo subagent-driven.
Fonti dettaglio (non ripetere qui): piano `docs/superpowers/plans/2026-07-19-ui-completamento.md`,
ledger `.superpowers/sdd/progress.md`, `REMEDIATION_LOG.md` (sez. 2026-07-21),
report gate `audit/UI_VERIFICA_REPORT.md` (v3) e `audit/E3_GATE_REPORT.md`.

- **Fase E2 — catena contratto (GATE superato):** test E2E fino al PDF + negativi;
  review R0 APPROVE-CON-FIX; sweep RBAC su 12 endpoint file/export. Finding chiusi
  NEW-021…028 (di cui NEW-022/024/025 di sicurezza: contratto/PDF timesheet/
  allegato email erano scaricabili da consultazione). NEW-026 resta admin-only
  per decisione utente.
- **Fase E1 — piano da template (GATE confermato dall'utente):** modello
  `PianoFinanziarioTemplate` + migration 060 (su DB reale) + bonifica relitti +
  seed 3 template reali; massimali con precedenza regola avviso validata (422
  cita l'articolo); endpoint + wizard UI 3 passi + fix review UX. Demo su clone:
  enforcement 422 "rif. Art. 12". Decisioni utente: NEW-032 ereditarietà avviso
  esplicitata in UI; NEW-033/034 API espone voce_codice/macrovoce/anno.
- **Fase E3 — Chiedi all'archivio (GATE dimostrato):** FTS dialect-aware +
  migration 061; endpoint search/chiedi con onestà non negoziabile (retrieval
  vuoto→non_presente senza LLM; citazioni validate server-side; LLM giù→
  degradato); UI 3 stati. Verifica empirica su clone: 10/10 query pertinenti;
  4/4 sinonimiche MISS → **pgvector raccomandato** (non implementato). NEW-037:
  domande in linguaggio naturale a `/chiedi` recuperano 0 risultati (AND dei
  lessemi) → oggi rendono `non_presente`; fix a basso costo, aperto.
- **GATE UI v3 SUPERATO** (codice/suite/demo su clone): matrice pagina×ruolo
  admin 20 / operatore 19 / consultazione 18; flussi 1–8 tutti OK (3 eccezioni v2
  chiuse). Dichiarazione: "TUTTE LE PAGINE COLLEGATE E FUNZIONANTI: SÌ" con
  eccezioni oneste. Review whole-branch: **ONDATA CHIUDIBILE** (nessun blocker
  di codice).

**Aperti a fine ondata (backlog, non bloccanti il gate):** NEW-029 (legacy_template_id
con dati), **NEW-030 (alta, fuori scope: azienda_ids/allievo_ids scartati su
/projects, sync links morto)**, NEW-031 (vista piani navigabile assente), NEW-035
(messaggio dedup), NEW-036 (corpus archivio vuoto in produzione), NEW-037 (query
NL su /chiedi), residui v2 UI-12/13/14/18, NEW-020. Raccomandazione pgvector.

**Decisioni utente (2026-07-21):** (1) Ondata M (manuale) → **NON avviata,
tenuta separata per dopo**. (2) attivazione runtime → **FATTA** (backend
riavviato + frontend ricostruito/ridispiegato; crawl browser non eseguibile
per libs mancanti, sostituito da verifica HTTP live). (3) NEW-037 e NEW-030 →
**FIXATI E CHIUSI** (`a7fa2d1`, `6bdb024`). Backlog residuo: NEW-029/031/035/036,
residui v2 (UI-12/13/14/18, NEW-020), raccomandazione pgvector.

Regole invariate: commit atomici mai push, migration solo Alembic provate su
copia, agenti solo proposte, nuovi problemi in FINDINGS_NUOVI, stop ai GATE.

## Lavoro corrente — programma giro completo

Prompt operativo avviato il 2026-07-17. Sequenza richiesta:

1. Ondata S — fix rapidi sicurezza.
2. V5 — ingestione dei quattro avvisi reali.
3. Ondata B — binding avviso → operatività.
4. Ondata L — case base, FTS, advisor e feedback loop.
5. Ondata C — fondamenta GDPR; CRM solo dopo prerequisito legale esterno.
6. Ondata F — rifiniture e dimostrazione end-to-end.

L'utente ha autorizzato preventivamente i gate tecnici e ha chiesto di non fermarsi per approvazioni. Eccezione: C1 richiede evidenza esterna che informative e LIA siano state predisposte; C2 non può essere attivata inventando tale fatto.

## Ondata S — CHIUSA (dettaglio in REMEDIATION_LOG + STATUS_ARCHIVE)

- S1…S6 chiusi (token firmati, SecurityAuditLog redatti, `.env` sample, HMAC
  WhatsApp, rendicontazione in `services/`, pin dipendenze). Ultimo commit
  applicativo `b335d1d`. Suite chiusura 530 passed. Residui: NEW-012 (worktree
  separata), NEW-013 (monitor performance legacy). Storico completo spostato in
  `STATUS_ARCHIVE_2026H1.md`; questo file resta sintetico (≤200 righe).

## V5 — gate file sorgente (in attesa deposito)

- `imports/avvisi/` contiene solo `README.md`: ingestione dei 4 avvisi reali
  (FAPI 3-2026, Fondimpresa 3/2026 e 4/2026, Formazienda 9/2022 rev.9) **non
  avviata** finché mancano i file. Pipeline prevista: upload → pulizia →
  segmentazione → estrazione LLM per categoria → `AgentSuggestion` (no
  validazione automatica).
- Infrastruttura V5 già pronta e testata (dettaglio in REMEDIATION_LOG):
  disattivazione sicura da Archivio Risorse (`03457e1`) e hard-delete protetto
  con doppia conferma (`d7e710f`, `c9ce6fd`), provato su copia temporanea.
  Nessuna cancellazione definitiva sul DB reale: Formazienda 2/2025 (ID 1)
  resta disattivato in attesa di conferma admin dalla UI.

## Sottosistema A — attività predittive CHIUSO

- ATT-01…ATT-07 completati: playbook versionati, checklist per fase,
  `activity_planner`, `procedure_extractor`, apply umano e `AttivitaEvento` append-only.
- Collector proposal-only e trigger esclusivamente manuali; nessun cron aggiunto.
- API `/api/v1/attivita` registrata con RBAC globale e locale: consultazione legge,
  operatore gestisce attività, solo admin modifica playbook.
- Migration `058` provata su clone con upgrade/downgrade/re-upgrade, dati invariati,
  5/5 tabelle e 5/5 indici; poi applicata al DB reale dopo backup cifrato verificato
  `/app/backups/gestionale_backup_att07_pre_migration_20260718_112650.sql.zip.gpg`.
- Gate mirato ATT: **35 passed**. Suite completa: **568 passed, 3 skipped**;
  gli skip sono i 2 monitor performance NEW-013 e il test PostgreSQL-only DOM-21.
- Il confutatore ha trovato un bypass admin nell'apply generico `playbook_voce`:
  corretto e coperto; verdetto **VALIDATO**, verifica indipendente **100 passed**,
  nessun blocker residuo. Riserve aperte documentate in NEW-014…NEW-017.
- Runtime post-migration: backend e worker healthy, `/health` 200, schema `058` senza drift.
- Evidenze: `audit/ATTIVITA_PREDITTIVE_GATE_2026-07-18.md`; design e piano tracciati
  sotto `docs/superpowers/`. Prossimi sottosistemi predittivi B/C/D richiedono spec separate.

## Ondata UI v1 — sintesi storica

- GATE UI v1 non superato (blocker UI-01…UI-17, poi chiusi al v2); dettagli nel
  report `audit/UI_VERIFICA_REPORT.md` e in `REMEDIATION_LOG.md`.
- Utenti test nel DB reale ancora presenti: `ui_test_admin`, `ui_test_operatore`,
  `ui_test_consultazione`, `ui_test_op_legacy`; password random non conservate.

## Regole di lavoro

- Codice nuovo nei servizi di dominio; vietato aggiungere funzioni a `backend/crud.py` root.
- Commit atomici locali `feat/fix(ID): ...`; mai push.
- Ogni modifica con test; suite completa verde a fine punto/ondata.
- Migration esclusivamente Alembic, prima provata su copia DB con verifica dati e drift.
- Nuovi problemi in `audit/FINDINGS_NUOVI.md`.
- LLM e agenti propongono soltanto; applicazione sempre umana.
- Preservare modifiche preesistenti e usare staging selettivo.

## Prompt di ripresa — copia operativa

Riprendi PythonPro da `/DATA/progetti/pythonpro`. Leggi prima `STATUS.md`, la sezione più recente di `REMEDIATION_LOG.md`, `audit/FINDINGS_NUOVI.md` e gli ultimi 10 commit. Non rifare Ondata S: è chiusa, ultimo commit applicativo `b335d1d`. Non fare push e preserva la worktree separata `.worktrees/email-agent`.

### 1. Ondata V5 — quattro avvisi reali

- Verifica in `/DATA/progetti/pythonpro/imports/avvisi` la presenza di: FAPI 3-2026, Fondimpresa 3/2026, Fondimpresa 4/2026, Formazienda 9/2022 rev.9. Se manca anche un file, fermati indicando il path esatto.
- Per ogni file esegui upload → pulizia → segmentazione → estrazione LLM per categoria → AgentSuggestion. Nessuna validazione automatica.
- Correggi pulizia/segmentazione se il rumore reale rompe la pipeline; test sul caso reale.
- Produci quattro report: regole proposte, confidence media, sezioni problematiche e qualità onesta. Fermati al GATE V5 per validazione UI dell'utente; le ondate successive devono tollerare validazione parziale.

### 2. Ondata B — binding avviso/operatività

- B1: scadenze avviso validate in job, notifiche, Agenda/HomeCockpit e suggestion per tassative senza azione.
- B2: massimali/parametri costo validati alimentano piani con precedenza avviso > fondo > warning; violazioni bloccanti citano articolo/testo.
- B3: regole documentali → proposta checklist additiva → apply umano crea `DocumentoRichiesto`.
- B4: prima GATE design; poi pulizia relitti template, nuova entità versionata `PianoFinanziarioTemplate`, seed da costanti, selezione da avviso e bonifica `Avviso.template_id`. Migration solo su DB copia.
- B5: agente timesheet guard proposal-only, warning default, enforcement separato false; GET generativo timesheet → POST con deprecazione.
- B6: migrazione identità ente/avviso a FK con report non matchati; fix dedup JSON/N+1 certification agent.
- Demo completa su DB copia e GATE Ondata B.

### 3. Ondata L — archivio e apprendimento

- L1: case base privo di PII, FTS PostgreSQL italiano, 10 query reali e gate empirico FTS/pgvector; UI “Chiedi all'archivio” con citazioni obbligatorie e risposta zero-result sicura.
- L2: `avviso_advisor` collector puro con rischi da esiti storici, solo suggestion.
- L3: feedback accept/reject, proposta taratura soglie, few-shot solo regole validate non superate/rifiutate, pattern errori; vietati fine-tuning, PII grezza e auto-apply.
- Demo e GATE Ondata L.

### 4. Ondata C — GDPR e CRM

- C1: basi giuridiche per allievi/referenti/legali rappresentanti, backfill “da qualificare”, report regolarizzazione, allegati tecnici DPIA/registro e retention 5-10 anni per fondo/rendicontazione.
- GATE C1 bloccante: C2 parte solo dopo conferma esterna di informative e LIA marketing B2B.
- C2 dopo conferma: timeline CRM, pipeline commerciale, `opportunity_finder` solo soggetti qualificati, storico partecipazioni/esiti. Demo e GATE C.

### 5. Ondata F — chiusura

- F1 smonta `sprint7.py`; F2 archivia docs e aggiorna documentazione piattaforme.
- F3 demo unica completa su DB copia dall'MD all'advisor/opportunity finder, con evidenze API/UI.
- F4 aggiorna `REMEDIATION_LOG.md` con “GIRO COMPLETO OPERATIVO: SÌ/NO” e riserve oneste.

## Memoria storica

- Storico precedente completo: `STATUS_ARCHIVE_2026H1.md`.
- Decisioni/verifiche dettagliate: `REMEDIATION_LOG.md`.
- Findings: `audit/FINDINGS_NUOVI.md`.
- Analisi guida: `audit/ANALISI_ARCHITETTURA_2026-07-17.md`.
