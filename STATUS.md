# PythonPro — Stato corrente

**Aggiornato:** 2026-07-18 (sessione brainstorming layer predittivo)
**Branch:** `claude/platform-audit-compliance-XnH86` (locale, nessun push)
**Percorso:** `/DATA/progetti/pythonpro`

## Stato operativo

- Runtime: backend, frontend, PostgreSQL, Redis e ARQ worker healthy.
- Schema: Alembic `057` head; ultimo check documentato senza drift.
- Baseline backend più recente: **530 passed, 2 skipped, 0 failed** su 532 test.
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

## Brainstorming layer predittivo — IN CORSO (2026-07-18)

Sessione interrotta dall'utente a metà brainstorming (skill superpowers:brainstorming).
Visione: piattaforma che apprende da avvisi/allegati/vademecum e dalle azioni degli
operatori per predire attività, assistere i piani e monitorare gli enti.

Decisioni già prese (confermate dall'utente, non ridiscutere):

1. Decomposizione in 4 sottosistemi: **A** procedura operativa predittiva (checklist
   attività per fase da avviso), **B** apprendimento da azioni operatori, **C** archivio
   piani presentati/approvati con punteggi per assistenza redazione, **D** monitoraggio
   automatico pagine enti/graduatorie/news. Ordine: A per primo; B/C/D spec separati dopo.
2. Sottosistema A: nuovo modello `AttivitaOperativa` — checklist per fase
   (presentazione/avvio/gestione/rendicontazione), agente propone, **apply umano**,
   operatore spunta; ponte eventi verso B.
3. Fonti di apprendimento: tutte e 4 — regole+scadenze validate V2, estrazione LLM da
   vademecum/manuali di gestione, playbook manuali curati, storico azioni operatori.
4. Scope MVP: tutte le fasi con profondità minima (struttura completa, contenuto cresce).
5. Approccio confermato: **playbook dichiarativo versionato in DB + motore di
   istanziazione** (agente `activity_planner` collector puro su regole/scadenze validate
   + playbook → AgentSuggestion → apply umano; agente `procedure_extractor` da
   vademecum → proposte voci playbook; event log `AttivitaEvento` per B). RAG solo come
   complemento futuro, niente hard-code per fondo.

Prossimo passo alla ripresa: presentare design a sezioni (architettura, modelli,
agenti, data flow, error handling, test) → approvazione → spec in
`docs/superpowers/specs/2026-07-18-attivita-predittive-design.md` → writing-plans.
Nota integrazione: A tocca i temi di Ondata B (B3 checklist documentale) e Ondata L
(apprendimento) del programma giro completo — riconciliare in fase di design.

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
