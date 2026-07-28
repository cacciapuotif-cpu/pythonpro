# PythonPro — Stato corrente

**Aggiornato:** 2026-07-28 (UX-8 CHIUSO: backend, UI, confutazione live, commit)
**Branch:** `claude/platform-audit-compliance-XnH86` (locale, **nessun push**)
**Percorso:** `/DATA/progetti/pythonpro`

> ⚠️ **Due sessioni hanno lavorato su questo branch il 27/07 in parallelo.**
> Questo file è scritto a quattro mani: la sezione "RIPARTENZA" qui sotto
> riguarda l'ondata UX; il resto del file traccia l'altro filone.

## ▶️ ONDATA UX OPERATIVA — stato al 2026-07-28

### Modo di lavoro concordato con l'utente

> *"parti dal punto 1: quando è verificato e il confutatore dà ok, passa al
> secondo punto e così via."*

Ogni punto si chiude solo dopo una **verifica che prova attivamente a
smentirlo**, non dopo un test che si limita a confermarlo. Esempio reale di
questa sessione: le associazioni del progetto 11 sembravano corrette, ma il
progetto 12 rispondeva identico; solo il confronto riga-per-riga col DB su
quattro progetti diversi (5, 11, 13, 1) ha escluso che l'endpoint ignorasse
`project_id`. Senza quel passo il punto sarebbe stato chiuso a torto.

### ✅ Punto 1 — Attivazione runtime: FATTA E VERIFICATA

Il runtime non gira più su codice vecchio. Comandi eseguiti:

```bash
export DOCKER_CONFIG=/tmp/dockercfg && mkdir -p "$DOCKER_CONFIG"   # /DATA/.docker non è scrivibile
docker compose up -d --force-recreate --no-deps frontend
docker restart pythonpro_backend
```

Confutazione superata su 7 fronti:

| Verifica | Esito |
|---|---|
| Container frontend sulla nuova immagine | `d7902ae0bd8c` → `69f6ca8899f8` |
| Bundle servito | `main.51462523.js` → `main.9c62b80d.js` |
| `/health` e frontend `/` | 200 e 200, entrambi healthy |
| openapi rotte project-scoped | `/projects/{id}/upload-convenzione`, `/confirm-convenzione`, `/fondimpresa/upload-ammissione`, `/upload-riepilogo` presenti |
| `schemas.Project` | espone `aziende_coinvolte` e `allievi_coinvolti` |
| **Dati live vs DB** | prog 5 → 2 az/0 all, 11 → 5/4, 13 → 5/0, 1 → 0/0: **combacia riga per riga**, l'endpoint discrimina davvero per progetto |
| UX-6 non crea gemelli | nessun `db.add(models.Project(...))` nel percorso project-scoped; c'è una guardia 409 se il `codice_fapi` appartiene a un altro progetto |
| Bundle chiama il percorso giusto | `"/projects/".concat(e,"/upload-convenzione")` presente nel bundle servito |

**UX-6 e UX-7 sono ora vivi anche sull'app in esecuzione**, non solo nel codice.

Da sapere per le sessioni future: per interrogare le API live servono
credenziali che **non esistono in chiaro** (le password `ui_test_*` sono random
e non conservate, e `ADMIN_DEFAULT_PASSWORD` in `.env` non corrisponde più
all'utente `admin` reale). Il JWT si genera con la stessa funzione dell'app,
senza toccare il DB:

```bash
docker exec pythonpro_backend python -c "
from datetime import timedelta
from auth import SecurityUtils
print(SecurityUtils.generate_token(data={'sub':'ui_test_admin','role':'admin'}, expires_delta=timedelta(minutes=30)))"
```

### ✅ Punto 2 — UX-8 dissociazione: CHIUSO il 2026-07-28

Commit: `99213df` (backend), `dd834a0` (UI), `be8c00f` (findings).

**Scoperta che ha cambiato la specifica.** Lo STATUS precedente dava per buone
guardie su "presenze" e "timesheet". Nel dominio reale **non esistono**:
`attendances` traccia i *collaboratori* e i timesheet pendono da `assignment`,
non da `allievo`. Le uniche tracce di un allievo su un progetto sono la riga
`allievo_project` (`ore_frequentate`, `stato`, `attestato_emesso`) e
`dati_retributivi`. Le guardie sono state ridefinite su questi fatti.

**Decisioni dell'utente** (da non rimettere in discussione):

| Domanda | Risposta |
|---|---|
| Cosa blocca la dissociazione di un allievo | `attestato_emesso` → **blocco assoluto, non forzabile nemmeno da admin**; `ore_frequentate > 0` → blocco **forzabile**; righe in `dati_retributivi` → blocco **forzabile**. `stato` da solo **non** è una guardia. |
| Azienda con suoi allievi ancora sul progetto | **Blocco, nessuna cascata implicita**: 409 con l'elenco degli allievi da staccare prima |
| Il PUT progetto che dissociava in silenzio | **Stesse guardie applicate anche al PUT**, in un servizio condiviso |

**Codice.** `backend/services/dissociazione_progetto.py` tiene le guardie in un
posto solo e non conosce HTTP; `DELETE /projects/{id}/allievi/{allievo_id}` e
`.../aziende/{azienda_id}` sono la via esplicita (forzatura riservata all'admin,
motivo ≥ 10 caratteri, audit su esito bloccato **e** riuscito); il PUT passa
dalle stesse guardie ma **non può forzare**. Sul frontend il pannello
"Associazioni" (`components/GestioneAssociati.js`) elenca aziende e allievi con
l'azione di distacco, mostra i messaggi del 409 e propone la forzatura solo se
il backend la dichiara superabile **e** l'utente è admin.

**Verifiche.**

| Cosa | Esito |
|---|---|
| Suite backend completa (`pytest tests/`, 20 min) | **861 passed, 6 skipped, 0 failed** |
| Delta vs baseline 821 | +39 (`test_ux8_dissociazione.py`) +1 (nuovo in `test_ux7`) — quadra esattamente |
| Suite frontend | **183 passed, 21 suite**; build di produzione verde |
| Mutation check sulla suite | `attestato → forzabile=True` ⇒ **2 test rossi**; file ripristinato |
| Confutazione live | 10 prove su progetti di prova, vedi `audit/FINDINGS_NUOVI.md` |
| Runtime | backend riavviato (rotte UX-8 in openapi), frontend ricostruito, bundle **`main.9c025a26.js`** con `Forza dissociazione` e le DELETE giuste |

La confutazione live è servita costruendo uno stato bloccante ad arte: sul dato
reale tutti gli 8 link hanno `ore_frequentate = 0`, `attestato_emesso = false` e
`dati_retributivi` è vuota, quindi nessuna guardia sarebbe scattata. Due
progetti di prova (14 e 15) creati, usati e **cancellati**: il DB è tornato a 7
progetti e 8 righe `allievo_project`, identico a prima.

La prova che conta: lo **stesso allievo** si stacca senza problemi da un
progetto dove non ha attestato (200) e resta bloccato su quello dove ce l'ha
(409) — la guardia legge il link `(progetto, allievo)`, non l'allievo.

**Limite dichiarato:** nessuna verifica con browser reale (chromium headless
qui è privo di `libatk-1.0.so.0`). La UI è verificata da 10 test jest, dalla
presenza nel bundle servito e dal montaggio in `ProjectManager.js:1516`.

**Due difetti nuovi, registrati e non corretti** (`audit/FINDINGS_NUOVI.md`):
il 403 sulla forzatura non lascia traccia in audit; `DELETE /projects/{id}` è un
soft-delete che si annuncia come eliminazione e conserva le associazioni.

**Da segnalare:** il progetto **11** (quello bonificato, con CUP e allievi) ha
`is_active = false` mentre il doppione **12** è attivo — l'elenco di default
mostra il doppione e nasconde il buono. Non causato da UX-8, nessuna modifica
fatta.

### ▶️ DA FARE, in quest'ordine

1. **UX-9** — albero di selezione allievi a cascata per azienda. Non iniziato.
   `Allievo.azienda_cliente_id` porta già il raggruppamento: non serve una
   seconda chiamata. (`AllievoCoinvolto` lo riespone nello schema.)
2. Poi **UX-5** (gate dominio date, **da presentare prima di scrivere codice**)
   → UX-0 → UX-1 → UX-2 → UX-3 → UX-4 → gate finale.

Verificato contro il codice il 2026-07-28: UX-5, UX-0, UX-1, UX-2, UX-3 e UX-4
non sono iniziati (nessun `data_avvio_piano` in `models.py`, nessun componente
di vista dettaglio condiviso, nessun router di profilo utente, nessuna entità
Sede/ContoCorrente, calendario senza filtri, collaboratori senza filtro
progetto).

### Fatto nelle sessioni precedenti

| | |
|---|---|
| NEW-039 | Suite era **rossa a HEAD** (6 failed): `757e83c` aveva aggiunto i kwargs `provider=`/`model=` alla chiamata LLM senza aggiornare i doppi di test; il `TypeError` finiva nell'`except Exception` dell'estrattore e passava per "sezione fallita". Chiuso (`8b313d9`). **Nota aperta:** quell'`except` troppo largo, in produzione, maschererebbe un errore di firma come estrazione vuota. |
| Lavoro pendente | Working tree sporco di sessione precedente, committato in 3 commit atomici: `bd41bf5` dedup multi-istanza AgentSuggestion, `166e558` DOM-08/DOM-18 piano congelato (migration 063, già applicata al DB reale), `b65dd0d` NotificationSystem montato via AppRoot. |
| UX-6 | **Chiuso** (`0fcb8a5`, `fcadc1a`). L'atto caricato dentro un progetto creava un gemello: il modale chiamava gli endpoint project-less, il cui confirm fa `db.add(models.Project(...))` senza ricevere `project_id`. Aggiunto il percorso project-scoped (FAPI + Fondimpresa) con diff campo-per-campo e guardia 422 sul documento non riconosciuto. |
| UX-7 | **Chiuso** (`b1c5ae3`). Le associazioni si salvavano ma `schemas.Project` non dichiarava `aziende_coinvolte`/`allievi_coinvolti`, che la scheda legge: sempre `undefined` → "nessun associato" a prescindere dai dati. Corretto anche un N+1 reale su `azienda_ids`. |
| Bonifica UX-6 blocco A | **ESEGUITA sul DB reale** (decisione utente): CUP `G64D26000610003` e i 4 allievi travasati dal progetto 12 al progetto 11, con `stato` e `ore_frequentate` preservati. Nulla distrutto: il 12 è ancora intatto. |

### Baseline al momento dello stop precedente (2026-07-27 ~17:00)

backend **821 passed, 6 skipped, 0 failed**; frontend **173 passed, 20 suite**;
build di produzione verde; alembic head `063`; working tree pulito; ultimo
commit dell'ondata `b1c5ae3`.

### GATE ancora aperti

- **UX-6, blocchi B e C.** Decisione utente: *"blocco A ora, C dopo verifica"*.
  A è fatto; **B e C attendono conferma**. Query pronte in
  `audit/UX6_BONIFICA_PROPOSTA.md`. ⚠️ Il blocco C elimina i progetti 12 e 13, e
  `allievo_project.project_id` ha `ON DELETE CASCADE`: eseguirlo solo dopo aver
  verificato che il travaso del blocco A regga.
- **UX-5** — gate dominio sul modello date, da presentare prima di scrivere codice.
- **UX-7** — nessun recupero dati necessario (le associazioni erano già sulla
  relazione canonica): il gate si chiude con la sola presa d'atto.

### Attenzioni

- **Le sedi operative aziende (`81a9b96`, altra sessione) toccano il territorio di
  UX-2c** (sedi multiple). Decisione utente: proseguire, ma **verificare cosa
  esiste già prima di attaccare UX-2**.
- **Ondata B è ancora aperta**: B6a e B5 fatti; **B1** (scadenze avviso), **B3**
  (checklist documentale) e **B6b** non fatti.
- Lo **scheduler dei backup si è fermato al 2026-07-25** (nessun daily il 26 e il 27).
  Backup manuale verificato di questa sessione:
  `/DATA/progetti/pythonpro_backup_pre_ux_20260727.sql`.
- `progetto_beneficiario` è un **relitto**: 0 righe, nessun riferimento nel codice
  applicativo. Da droppare in un giro di igiene.
- La suite backend completa impiega **15–24 minuti**: prevederlo, non scambiarlo
  per un blocco.

## Stato operativo

- Runtime: backend, frontend, PostgreSQL, Redis e ARQ worker healthy.
- Schema reale: Alembic **`063` head**, verificato con `alembic current` sul
  container il 2026-07-27 sera (template piani 060 + FTS archivio 061 + drop
  relitto legacy_template_id 062 + piano congelato DOM-08/DOM-18 063). Backend
  riavviato dopo 062 per riallineare il modello allo schema (il drop colonna
  dava 500 sui piani finché il processo caricava il vecchio modello).
- Baseline backend: **861 passed, 6 skipped, 0 failed** (al commit `99213df`,
  2026-07-28, 20 minuti di esecuzione).
- Baseline frontend: **183 passed, 21 suite**; build production verde.
- Frontend ridispiegato il 2026-07-28, bundle **`main.9c025a26.js`** (UX-8 UI).
  Backend riavviato lo stesso giorno per caricare le rotte di dissociazione.
- Ridispiegato in precedenza il 2026-07-27 sera, bundle **`main.9c62b80d.js`**:
  live allineato a UX-6 e UX-7 oltre che ai fix auth, sedi operative e import
  XLSX allievi. Il precedente `main.51462523.js` era costruito ma non servito.
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

## Fix sessione 401 concorrenti — LIVE (2026-07-27)

- Problema osservato da Aziende/Progetti/Allievi: più richieste parallele con
  access token scaduto avviavano ciascuna un refresh. Un singolo refresh
  fallito/rate-limited poteva cancellare i token e lasciare la UI aperta con
  tutti gli endpoint a `401`, bloccando anche il salvataggio delle sedi.
- `frontend/src/lib/http.js`: refresh reso single-flight; tutte le richieste
  concorrenti attendono e riusano la stessa operazione.
- Test regressione sui tre endpoint segnalati: un solo refresh, tre retry `200`.
  Gate mirato `6 passed`; suite frontend `154 passed`, 3 snapshot; build verde.
- Commit locale `0d879a8`; nessun push. Frontend ricostruito e ridistribuito,
  container healthy, bundle `main.37446b75.js`; backend health `200`.
- La sessione browser già invalidata richiede un solo nuovo login; dopo il
  caricamento del bundle aggiornato il problema concorrente non deve ripetersi.

## Fix sedi operative aziende/import XLSX — LIVE (2026-07-27)

- Caso reale: la UI dichiarava salvata la sede `Napoli` di Power Impianti, ma
  `AziendaClienteCreate/Update` non dichiaravano `sedi_operative`,
  `fund_memberships` e `project_ids`. Pydantic ignorava i campi extra, quindi
  il CRUD di sincronizzazione era irraggiungibile e la sede non entrava nel DB.
- Aggiunto contratto write/read completo per sedi e fondi; le risposte lista,
  dettaglio, create e update riespongono relazioni e ID usati dall'import
  allievi. Commit locale `81a9b96`, nessun push.
- Test API create/update/persistenza/listing aggiunti. Gate collegato:
  `45 passed`; sintassi e diff-check OK. Suite totale avviata senza failure nel
  blocco iniziale, poi interrotta perché ridondante e molto lenta sulle fixture.
- Backend riavviato e healthy; OpenAPI live conferma `sedi_operative` sia su
  update sia sulla risposta. Nessuna migration necessaria: tabella già a schema.
- Ripristinata con guardia anti-duplicato la riga persa:
  `Power Impianti srl` (ID 10) → `Napoli` (sede ID 1). L'import XLSX può usare
  esattamente `Power Impianti srl` / `Napoli`.

## Fix 422 import allievi XLSX — LIVE (2026-07-27)

- Dopo il ripristino della sede, il POST `/api/v1/allievi/bulk-import` arrivava
  al backend ma falliva con `422`: le celle data lette da ExcelJS come oggetti
  JavaScript `Date` venivano convertite in una stringa non valida e poi
  concatenate a `T00:00:00Z`.
- L'importatore ora normalizza oggetti `Date`, seriali Excel, date ISO e formati
  italiani `GG/MM/AAAA`, `GG.MM.AAAA`, `GG-MM-AAAA`; date impossibili vengono
  fermate prima dell'invio indicando la riga del foglio.
- Il frontend interpreta anche il formato `details` del gestore errori FastAPI:
  un eventuale 422 residuo mostra riga e campo (l'indice API zero-based viene
  tradotto nella riga Excel, intestazione inclusa) invece del messaggio generico.
- Commit locale `a25ef87`, nessun push. Verifica sul commit pulito: **18 suite,
  161 test, 3 snapshot**, build production verde. Deploy isolato dalle altre
  modifiche locali in corso; container frontend healthy, bundle
  `main.51462523.js`, backend health `200`.

## V5 — ingestione avvisi SBLOCCATA via LLM cloud (2026-07-24)

- Il locale (Ollama 7b su CPU, no GPU) estraeva 0 regole in 23 min → vicolo cieco.
- Provider LLM **anthropic** aggiunto a `ai_agents/llm.py` con override per-agente
  (`757e83c`): estrazione avvisi (documenti PUBBLICI) su cloud, agenti con PII
  restano su Ollama locale. `AVVISO_EXTRACTOR_LLM_PROVIDER=anthropic`,
  `AVVISO_EXTRACTOR_LLM_MODEL=claude-opus-4-8` in `.env` (key non committata);
  compose passa le env a backend/arq_worker (`1070a7f`). `anthropic==0.119.0`
  in requirements (immagine ricostruita).
- Estrazione reale FAPI (rev 7, 11k char): **Opus 4.8 ~90s → 44-48 regole**,
  Sonnet 5 ~74s → 21, locale 7b 23min → 0. Modello scelto: **Opus** (thoroughness;
  costo ~$0,38/avviso, trascurabile al volume reale). Proposte in AgentSuggestion
  → validazione umana → avviso_regole → archivio (sblocca NEW-036).
- Worker gunicorn `TIMEOUT=240` (`c17ae79`): l'estrazione sincrona cloud (~90s)
  superava i 60s → UI in timeout. **Backlog: estrazione asincrona ARQ** (fix
  definitivo; con async il modello lento non blocca la UI).

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
