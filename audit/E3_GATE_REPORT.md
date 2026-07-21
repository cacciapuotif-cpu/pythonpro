# GATE DI FASE E3 — Report + Verifica empirica FTS (Task E3.4)

- Data: 2026-07-21 (rieseguito e verificato empiricamente in modo indipendente)
- Branch: `claude/platform-audit-compliance-XnH86` (nessun push)
- Fase E3: ricerca FTS archivio (E3.1, migration 061), endpoint `search`/`chiedi`
  con citazioni obbligatorie e degrado onesto (E3.2), UI `ArchivioChiedi` (E3.3).
- Scopo: gate di fase E3 e chiusura del vecchio GATE V3 (verifica empirica FTS
  lessicale vs necessità di ricerca semantica/pgvector).

---

## 1. Suite, build, runtime

| Gate | Comando | Esito |
|------|---------|-------|
| Backend | `docker exec pythonpro_backend python -m pytest tests/ -q` | **725 passed, 5 skipped, 0 failed** (971s) |
| Frontend | `CI=true npm test -- --watchAll=false --runInBand` (host) | **14 suite / 123 test passed, 3 snapshot, 0 failed** |
| Build | `CI=true npm run build` | **Compiled successfully** — build pronto |
| Migration | `alembic current` su DB reale | **061 (head)** |
| Runtime | `GET /health` DB reale | **200** |

I 5 skip sono tutti gate d'ambiente, nessuno è un fallimento:
- 2 test archivio FTS PostgreSQL-only (`test_archivio_search.py`, richiedono
  `ARCHIVIO_FTS_TEST_DATABASE_URL`);
- 1 test DOM-21 attendance PostgreSQL-only;
- 2 test performance-monitor (`test_improvements.py`, NEW-013, `psutil` assente).

**Prova attiva del percorso PostgreSQL:** eseguendo `test_archivio_search.py` con
`ARCHIVIO_FTS_TEST_DATABASE_URL` = clone, i 2 PG-only **passano** → il file va da
"11 passed / 2 skipped" a **13 passed, 0 skipped** su Postgres reale. Migration
061 + indici GIN `to_tsvector('italian', …)` verificati su motore reale, non solo
sul fallback SQLite/ILIKE.

> Nota runtime importante: il backend girava con **codice pre-E3** (processo
> avviato prima dell'aggiunta dei file archivio del 21/07 10:31; `/openapi.json`
> non esponeva `archivio/*`, i curl davano 404). Ho **riavviato
> `pythonpro_backend`** → rotte `archivio/search` e `archivio/chiedi` registrate,
> `/health` 200. Nessuna scrittura, nessuna migration nuova, DB reale invariato.

---

## 2. Verifica curl 3 ruoli su DB reale

**Autenticazione:** le password dei `ui_test_*` sono random e **non conservate**
(STATUS.md). Ho generato i JWT con l'`SecurityUtils.generate_token` della stessa
app — identico a ciò che produce `/api/v1/auth/login`, stateless, **senza alcuna
scrittura sul DB reale**. Utenti presenti e attivi: `ui_test_admin` (admin),
`ui_test_operatore` (operatore), `ui_test_consultazione` (consultazione).

DB reale: 6 avvisi, 6 revisioni, **0 regole / 0 conoscenze / 0 esiti** (NEW-036).

| Endpoint | admin | operatore | consultazione |
|----------|-------|-----------|---------------|
| `GET /archivio/search?q=massimale docenza` | 200 · 0 risultati | 200 · 0 risultati | 200 · 0 risultati |
| `POST /archivio/chiedi` | 200 · `non_presente` | 200 · `non_presente` | 200 · `non_presente` |

Tutti e tre i ruoli leggono (RBAC corretto: la consultazione è lettura). Sul DB
reale `/chiedi` restituisce **`non_presente`** perché il retrieval è vuoto (fonti
vuote) e in quel caso **l'LLM non viene mai chiamato** (regola 1 di onestà).
Questo è lo stato reale e onesto della feature in produzione oggi.

### Stati di `/chiedi` — verifica onestà (su CLONE seedato, retrieval non vuoto)

| Scenario | Condizione | Stato reale ottenuto |
|----------|-----------|----------------------|
| Retrieval vuoto | query senza match / DB reale | **`non_presente`** (`risposta=None`, LLM mai chiamato) |
| LLM OFF (`AI_AGENT_LLM_PROVIDER=none`) | retrieval = 2 passaggi | **`degradato`** (`risposta=None`, `n_risultati=2`) |
| LLM ON (ollama `qwen2.5:1.5b`) | retrieval = 2 passaggi | **`degradato`** — la risposta LLM citava `massimale_orario_docenza` (la chiave) invece dell'id-passaggio `regola:2`; la validazione server-side ha **scartato** la citazione fuori-retrieval (regola 2 di onestà) |
| LLM ON, citazioni conformi | — | **`ok`** non raggiunto in pratica col modello locale 1.5b (non emette gli id nel formato richiesto); lo stato `ok` è coperto dai test unità con LLM mockato (`test_archivio_chiedi.py`) |

Osservazione onesta: con il modello locale piccolo lo stato `ok` non si è
raggiunto perché il modello non rispetta il formato degli identificatori — ma
questo è il **guard di onestà che funziona**: meglio `degradato` che una
citazione non verificabile. La ricerca ritorna sempre i passaggi.

---

## 3. Verifica empirica FTS — 10 query (CLONE seedato)

Il corpus reale è vuoto: la recall su dati veri **non è misurabile ora**. Per
provare il **motore** (non per inventare recall su produzione) ho clonato il DB
reale in `gestionale_e3gate_test` (`pg_dump gestionale | psql clone`, già a head
061; `gestionale` mai toccato) e inserito un corpus realistico minimo ma non
banale: **13 AvvisoRegola validate** (categorie `massimali`/`parametri_costo`/
`rendicontazione`/`presentazione`; chiavi `massimale_orario_docenza`/`tutoraggio`/
`coordinamento`, `cofinanziamento_minimo`, `iva_ammissibilita`,
`vincolo_macrovoce_erogazione`, `parametro_costo_ora_formazione`, …) + 1 regola
*proposta* di controllo (non deve emergere), distribuite su 3 fondi (FONDIMPRESA,
FAPI, Formazienda); **3 AvvisoConoscenza** (rendicontazione, documentazione
collaboratori, ammissibilità spese/scadenze); **2 AvvisoEsitoProgetto** (note).
Vincoli CHECK rispettati (regole validate con `validata_da_user_id`+`validata_il`,
categorie e stati ammessi).

Le 10 query eseguite via `search_archivio` con sessione sul clone (dialect
PostgreSQL → percorso `to_tsvector`/`websearch_to_tsquery`/`ts_rank`).

| # | Query | n_risultati | Fonte top (rank) | Pertinente? |
|---|-------|-------------|-------------------|-------------|
| 1 | massimale orario docenza | 2 | regola FONDIMPRESA (0.6054) | SÌ — ma **manca** la regola equivalente "formatori" di Formazienda (gap inter-fondo) |
| 2 | spese ammissibili tutoraggio | 2 | regola FAPI (0.3542) | SÌ |
| 3 | scadenza presentazione domanda | 1 | regola FONDIMPRESA (0.3968) | SÌ |
| 4 | cofinanziamento | 3 | regola FONDIMPRESA (0.0760) | SÌ (2 fondi + 1 esito) |
| 5 | rendicontazione a costi reali | 3 | regola FONDIMPRESA (0.8227) | SÌ (regola + conoscenza + esito) |
| 6 | IVA ammissibile | 1 | regola FONDIMPRESA (0.3223) | SÌ |
| 7 | massimale coordinamento | 2 | regola FONDIMPRESA (0.1566) | SÌ |
| 8 | documentazione obbligatoria collaboratori | 1 | conoscenza FONDIMPRESA (0.4300) | SÌ |
| 9 | parametri costo formazione | 1 | regola FONDIMPRESA (0.5651) | SÌ |
| 10 | vincoli macrovoce | 1 | regola FONDIMPRESA (0.2379) | SÌ |

Su match esatti/stemmati il motore è solido: **10/10 query hanno il top pertinente**,
ordinamento per `ts_rank` sensato (Q5 la più densa, 0.8227), la regola *proposta*
di controllo non compare (filtro `stato='validata'` corretto), la deduplica
multi-fonte funziona (Q4/Q5 attraversano regola+conoscenza+esito).

### Valutazione recall — dove la FTS lessicale fallisce

**1) Sinonimi inter-fondo (dimostrato).** Seed volutamente asimmetrico:
FONDIMPRESA e FAPI usano "docenza", Formazienda usa "formatori" per lo **stesso**
concetto. Risultato empirico:
- query `massimale orario docenza` → tocca **{FONDIMPRESA, FAPI}**, **non** Formazienda;
- query `formatori` → **1 solo** risultato (Formazienda), **non** trova le regole "docenza" di FONDIMPRESA/FAPI.

Gli stem italiani `docenza`→`docenz`, `docente`→`docent`, `formatori`→`format`
sono distinti: la FTS non li unifica. Un ufficio che cerca il massimale docenza
"tra tutti i fondi" **non vede** l'avviso che chiama la stessa voce "formatori".
È esattamente la ricerca inter-fondo obiettivo della feature.

**2) Domande in linguaggio naturale (NUOVO — NEW-037).** `websearch_to_tsquery`
mette in **AND** tutti i lessemi content. La domanda
`Qual è il massimale orario per la docenza?` diventa
`'qual' & 'massimal' & 'orar' & 'docenz'`: nessun documento contiene "qual" → match
**0** → `/chiedi` risponde `non_presente` **anche quando il contenuto pertinente
esiste** (verificato: la stessa query in forma keyword `massimale orario docenza`
dà 2 risultati). `/chiedi` soffre questo più della `search`, perché riceve
domande intere e non parole chiave. Dettaglio in NEW-037.

### Raccomandazione pgvector — **SÌ, riaprire (raccomandazione, NON implementazione)**

Le due classi di query che falliscono — sinonimi inter-fondo e domande in
linguaggio naturale — sono precisamente il dominio della ricerca semantica. Per la
**ricerca inter-fondo**, obiettivo dichiarato dell'ondata "archivio e
apprendimento", la FTS lessicale italiana da sola è **insufficiente**: trova match
esatti/flessi ma non avvicina termini equivalenti con lemmi diversi tra fondi.
Raccomandazione: reintrodurre a piano un layer embedding + pgvector (retrieval
ibrido lessicale+semantico, o ANN come rerank del top-k FTS). **Non implementato
in questa fase** — e prematuro finché le fonti reali sono vuote (NEW-036), su cui
non si può misurare il guadagno. La FTS resta la base corretta e portabile
(fallback ILIKE su SQLite = anche degrado runtime). Mitigazione tattica per
NEW-037, indipendente da pgvector: pre-processare la domanda in `/chiedi`
(estrazione parole chiave / `to_tsquery` in OR) prima della FTS.

---

## 4. Stato NEW-036 — corpus vuoto in produzione

`avviso_regole=0`, `avviso_conoscenze=0`, `avviso_esiti_progetto=0` sul DB reale
(a fronte di 6 avvisi / 6 revisioni). **La feature E3 è costruita, testata e
tecnicamente pronta, ma inerte in produzione**: finché non arriva l'ingestione
reale (validazione umana delle regole estratte dagli avvisi, inserimento di
conoscenze operative, registrazione esiti), `search` e `chiedi` restituiranno
correttamente 0 risultati / `non_presente`. Non è un difetto di codice: è un fatto
di dato. Resta **aperto** (dato, non codice).

---

## 5. Dichiarazione di chiusura fase E3 (onesta)

**E3 è CHIUDIBILE sul piano tecnico**, con eccezioni oneste documentate:

- CHIUSO: E3.1 FTS + migration 061 (provata su clone e su DB reale, head 061),
  E3.2 endpoint + degrado onesto, E3.3 UI. Suite backend/frontend verdi, build
  verde, runtime healthy, RBAC 3 ruoli 200 su `search` e `chiedi`, stati
  `non_presente`/`degradato` verificati empiricamente, guard citazioni
  funzionante (rifiuto server-side di id fuori retrieval osservato sul modello reale).
- ECCEZIONE DATO (NEW-036): corpus vuoto in produzione → feature inerte finché
  non arriva l'ingestione reale. Blocco **non di codice**.
- RACCOMANDAZIONE RECALL (pgvector): la FTS lessicale non copre la ricerca
  semantica inter-fondo né le domande in linguaggio naturale; per l'obiettivo
  "ricerca tra fondi" va riaperto a piano un layer semantico. **Non implementato.**
- NUOVO (NEW-037): `/chiedi` passa la domanda grezza a `websearch_to_tsquery`
  (AND di tutti i lessemi) → domande verbose recuperano 0 → `non_presente`
  ingiustificato. Mitigazione a basso costo indicata.

In sintesi: **la costruzione software della fase E3 è completa e verde**; il
valore in produzione dipende dall'ingestione dei dati (NEW-036) e la copertura di
recall inter-fondo richiede il layer semantico (pgvector), oggi solo raccomandato.

---

## 6. Integrità DB reale e teardown

- Clone `gestionale_e3gate_test`: creato, seedato (13 regole/3 conoscenze/2 esiti),
  interrogato e **droppato** a fine verifica.
- DB reale `gestionale`: **mai toccato in scrittura**; fonti 0/0/0 invariate;
  head Alembic 061 invariato; `/health` reale → 200.
