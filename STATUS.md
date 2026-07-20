# PythonPro — Stato corrente

**Aggiornato:** 2026-07-20 (ONDATA UI-COMPLETAMENTO ripresa: R0+R1+E2.2 chiusi, GATE FASE E2 superato)
**Branch:** `claude/platform-audit-compliance-XnH86` (locale, nessun push)
**Percorso:** `/DATA/progetti/pythonpro`

## Stato operativo

- Runtime: backend, frontend, PostgreSQL, Redis e ARQ worker healthy.
- Schema reale: Alembic `059` head.
- Baseline backend: **578 passed, 3 skipped, 0 failed** su 581 test.
- Baseline frontend: **96 passed, 3 snapshot, 0 failed**; build production verde.
- V1 archivio avvisi e V2 pipeline ingestione sono chiuse.
- Wave dominio 1 e Wave 2.1 timesheet snapshot immutabile sono chiuse.
- Flusso agenti canonico attivo: collector puro → AgentRun/AgentSuggestion → approvazione umana → apply auditato. Nessun auto-apply.
- `AGENT_DATA_RETENTION_ENABLED=false` resta invariato.
- History Git contiene vecchi `.env`: **MAI push** finché non viene ripulita con procedura dedicata.

## Ondata UI-FIX — stato al GATE v2

- FIX-1…8 completati con commit atomici locali e test di regressione UI/
  integrazione: `cbb255a`, `396765c`, `c63ebdd`, `1e027c1`, `c06ae57`,
  `23ad325`, `53e6e39`, `8058f57`.
- Il crawl v2 ha trovato UI-20/NEW-019 (Dashboard consultazione → reporting
  timesheet 403), corretto in `6065fe5` con test ruolo×chiamata.
- Crawl definitivo: utenti canonici 3/3, menu 18/17/16, pagine pertinenti
  19/18/17, **0 errori console, 0 errori network, 0 spinner**.
- UI-3: 123 test mirati verdi; clone PostgreSQL con 4/4 piani apribili, 9/9 PDF
  timesheet e snapshot congelato 1/1; Home 5/5 destinazioni/filtri corretti.
- Stato estrazione onesto in migration 059: `completata/parziale/fallita`,
  sezioni/categorie/scarti e retry delle sole parti mancanti. DB reale: sei
  revisioni tutte `caricato`, quindi nessun backfill inventato.
- Backup pre-fix verificato:
  `/app/backups/gestionale_backup_ui_fix_pre_20260719_103215.sql.zip.gpg`.
- Ambiente clone `pythonpro_ui059_test` e backend temporaneo rimossi; stack reale
  healthy, `/health` 200, DB reale ancora 6 revisioni e 4 piani.
- Report v2 completo e confronto prima/dopo:
  `audit/UI_VERIFICA_REPORT.md`.
- **Verdetto: GATE UI v2 NON SUPERATO; TUTTE LE PAGINE COLLEGATE E FUNZIONANTI:
  NO.** Le pagine esistenti sono pulite, ma restano tre eccezioni:
  1. creazione piano da template assente (B4);
  2. catena contratto priva di un'unica prova E2E fino alla generazione;
  3. “Chiedi all'archivio” con citazioni assente (L1).
- NEW-020 aperto: health frontend non portabile su hostname pubblico same-origin;
  il deploy locale/LAN corrente non è coinvolto.
- **Ondata M congelata.** Prossimo passo: decisione utente sull'accettabilità
  delle tre eccezioni oppure completamento B4/L1 e test contratto prima del manuale.

## Ondata UI-COMPLETAMENTO — IN CORSO, FASE E2 CHIUSA (2026-07-20)

Obiettivo: chiudere le 3 eccezioni del GATE UI v2 e rieseguire GATE UI v3.
Ordine: **E2 → E1 → E3 → GATE v3**. Ondata M resta congelata fino a v3 superato.

**Piano completo (fonte unica dei task):**
`docs/superpowers/plans/2026-07-19-ui-completamento.md`
Metodo: subagent-driven (team QA e2e, frontend React, backend, data engineer,
UX reviewer). Brief per task già estratti in `.superpowers/sdd/briefs/`;
ledger avanzamento in `.superpowers/sdd/progress.md`.

**Fatto:**
- Ricognizione completa (sezione "Ricognizione" nel piano — NON ripeterla):
  B4 inesistente; FTS inesistente; trigger reale contract_agent già presente
  nella `valida` documenti; massimali solo `MassimaleFondo` (precedenza regola
  avviso da costruire in E1.3); pdfminer disponibile per estrazione testo PDF.
- Backup fresco verificato:
  `/app/backups/gestionale_backup_ui_completamento_pre_20260719_143401.sql.zip.gpg` (INTEGRITY=True).
- **Task E2.1 CHIUSO dall'implementer** (test E2E catena contratto fino al PDF):
  commit `3274988` (test), `2039703` fix NEW-021 (accept umano rotto per
  suggestion non-collaborator), `7f6b170` fix NEW-022 (download contratto
  negato a consultazione). Suite completa: **581 passed, 3 skipped, 0 failed**.
  Findings NEW-021/NEW-022 censiti e chiusi in `audit/FINDINGS_NUOVI.md`.
  Report: `.superpowers/sdd/briefs/task-E2_1-report.md`.
- **Review R0 di E2.1 (2026-07-20): APPROVE-CON-FIX**, findings tutti chiusi:
  NEW-023 guardia di stato su accept diretto (`78d40a3`), matrice RBAC
  frontend allineata su `/contract` (`20c35e5`).
- **Task R1 sweep RBAC file/export (2026-07-20)**: censiti 12 endpoint.
  NEW-024 PDF timesheet negato a consultazione (`b107046`); NEW-025 allegato
  email inbox negato a consultazione (`beeb22c`); test parametrizzato
  ruolo×endpoint `test_rbac_download_endpoints.py`, 73 test (`2bb0468`).
  **NEW-026 APERTO — decisione utente**: export CSV timesheet massivo oggi
  admin-only esplicito; matrice Ondata 1 direbbe operatore. Non ampliato.
- **Task E2.2 test negativi (2026-07-20)**: doc mancante/non validato/scaduto
  (`ad256cc`). NEW-027 doc scaduto completava la pratica → fix collector
  (`fa75b30`); NEW-028 suite non isolata dal rate limiter → `tests/conftest.py`
  (`137fecd`). Doppio accept già coperto dal test NEW-023.
- **Task E2.3 GATE FASE E2 SUPERATO (2026-07-20)**: suite backend
  **658 passed, 3 skipped, 0 failed**; frontend **97 passed, 3 snapshot**.
  Nota design confermata: `genera_contratto` indipendente dallo stato
  workflow (download = azione operatore, mai auto-apply).

**Resta da fare (in ordine, dal piano):**
1. E1.1 modello `PianoFinanziarioTemplate` + migration 060 (prova su clone,
   poi DB reale) + seed idempotente; E1.2 endpoint listing/anteprima/
   from-template; E1.3 massimali con precedenza regola avviso validata e
   citazione articolo; E1.4 wizard UI 3 passi; E1.5 gate fase E1.
2. E3.1 servizio ricerca FTS + migration 061 (fallback ILIKE per SQLite);
   E3.2 endpoint search + chiedi (onestà: retrieval vuoto → "non presente"
   senza LLM; citazioni obbligatorie validate server-side; LLM giù → degrado
   pulito); E3.3 pagina "Chiedi all'archivio" (3 ruoli, disclaimer, citazioni
   cliccabili); E3.4 gate fase E3.
3. GATE UI v3: G3.1 riesecuzione matrice pagina×ruolo + flussi 1–8 + suite
   complete; G3.2 report v3 (confronto v1→v2→v3, dichiarazione onesta) +
   REMEDIATION_LOG; G3.3 se superato → sbloccare e avviare Ondata M
   (manuale con capitoli 3 e 9), altrimenti fermarsi con elenco onesto.
4. Review finale whole-branch prima di chiudere l'ondata.

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

## Ondata S — stato

- Memoria letta: `REMEDIATION_LOG.md`, precedente `STATUS.md`, `audit/FINDINGS_NUOVI.md`, `audit/ANALISI_ARCHITETTURA_2026-07-17.md`, ultimi 20 commit.
- Backup fresco verificato: `/app/backups/gestionale_backup_ondata_s_pre_20260717_162634.sql.zip.gpg` (`INTEGRITY=True`).
- Riorganizzazione stato: storico completo spostato in `STATUS_ARCHIVE_2026H1.md`; questo file resta sintetico e deve rimanere entro 200 righe.
- S1 chiuso: token random firmati, scadenza 24h, confronto constant-time e input malformati fail-closed (`41b6048`, `80d4b01`).
- S2 chiuso: snapshot `SecurityAuditLog` redatti e retention 24 mesi configurabile via proposta `data_retention`, apply solo umano (`c423669`). Kill switch invariato disattivo.
- S3 chiuso sul branch corrente: `.env.development` convertito in sample con placeholder; runtime pulito; backup env riemerso archiviato in `/DATA/progetti/pythonpro-local-archive/2026-07-17_ondata_s/` (`26ff969`). Residuo worktree separata = NEW-012.
- S4 chiuso: firma WhatsApp HMAC-SHA256 sul raw body, compare constant-time e input malformati fail-closed (`3683d48`).
- S5 chiuso dopo conferma utente (`b5173e1`): generatore spostato in `services/rendicontazione.py`, endpoint `POST /api/v1/reporting/projects/{id}/rendicontazione`, RBAC admin/operatore, fondo da FK avviso con fallback legacy, isolamento buste paga per azienda e nomi ZIP anti-path-traversal. Gate mirato: **81 passed**.
- S6 chiuso in tre commit: pulizia schema/parser/docs (`ccebe9e`), attivazione e
  riallineamento degli 8 test legacy (`6f77534`), fonte unica dipendenze pin (`b335d1d`).
- Gate Ondata S superato: test mirati S5/S6 verdi; Compose valido; immagini backend e
  worker costruite; `pip check` e import runtime OK; suite completa **530 passed,
  2 skipped, 0 failed**; Alembic `057 (head)` senza drift.
- I 2 skip riguardano il monitor performance legacy non disponibile nel runtime;
  residuo censito come NEW-013. Ondata S **CHIUSA**; prossimo punto V5.

## V5 — gate file sorgente

- Verifica eseguita il 2026-07-18: `imports/avvisi` contiene soltanto `README.md`.
- Ingestione non avviata, come da gate: se manca anche un documento bisogna fermarsi.
- File markdown UTF-8 richiesti nei seguenti percorsi convenzionali:
  - `imports/avvisi/fapi_3-2026.md`
  - `imports/avvisi/fondimpresa_3-2026.md`
  - `imports/avvisi/fondimpresa_4-2026.md`
  - `imports/avvisi/formazienda_9-2022_rev9.md`
- Dopo il deposito: verificare contenuti, poi upload → pulizia → segmentazione →
  estrazione LLM per categoria → `AgentSuggestion`, senza validazione automatica.
- Primo tentativo UI Formazienda del 2026-07-18 ha esposto due bug, entrambi chiusi:
  revisioni legacy con sorgente nulla causavano `500` mascherato come CORS e il
  client inviava il `FormData` come JSON causando `422` (`70713f1`).
- Aggiunta disattivazione sicura da Archivio Risorse (`03457e1`): pulsante con
  conferma, soft-delete `is_active=false`, storico conservato, endpoint riservato
  ad Admin/Manager e liste operative che mostrano solo avvisi attivi.
- Gate mirati upload/disattivazione: backend V2 API **7 passed**; frontend
  archivio/API **5 passed**. Backend e frontend ricostruiti e healthy.
- L'utente ha poi disattivato Formazienda `2/2025` (ID 1) e chiesto cancellazione
  permanente. Audit read-only: record non orfano, collegato al progetto ID 2 `pinco`,
  piano finanziario ID 2 e revisione corrente ID 2. Il tentativo upload precedente
  era fallito con 422 e non ha creato una nuova revisione.
- Hard-delete protetto completato (`d7e710f`): visibile solo agli Admin, anteprima
  obbligatoria di progetti, piani, revisioni/documenti collegati, prima conferma e
  seconda conferma con frase esatta. Progetti e piani restano nel sistema ma vengono
  scollegati; avviso, revisioni, regole, scadenze, documenti, conoscenza, esiti e file
  sorgente vengono eliminati. Agent run/suggestion e audit restano conservati.
- Gli Admin vedono anche gli avvisi disattivati, marcati `Disattivato`, così il
  comando definitivo resta raggiungibile dopo il soft-delete (`c9ce6fd`). Manager e
  altri ruoli continuano a vedere soltanto la lista operativa attiva.
- Prova distruttiva superata esclusivamente sulla copia PostgreSQL temporanea
  `gestionale_v5_harddelete_test`: avviso 1 rimosso, progetto 2 e piano 2 presenti e
  scollegati, audit `avviso_hard_delete` presente. Copia temporanea eliminata subito.
- Gate hard-delete: backend V2 API **8 passed**; frontend archivio/API **9 passed**.
  Build/recreate completati; backend healthy, `/health` 200, frontend HTTP 200.
- Nessuna cancellazione definitiva eseguita sul database reale: Formazienda 2/2025
  ID 1 resta disattivato e attende la doppia conferma dell'amministratore dalla UI.

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
