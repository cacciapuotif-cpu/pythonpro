# GATE FASE E3 — "Chiedi all'archivio" (FTS + endpoint + UI)

**Data:** 2026-07-21
**Branch:** `claude/platform-audit-compliance-XnH86` (locale, nessun push)
**Head Alembic:** `061` (indici FTS archivio)

Chiude la fase E3 dell'ondata UI-COMPLETAMENTO e assorbe la vecchia riserva
"verifica empirica FTS" del GATE V3.

## 1. Suite e build

| Suite | Esito |
|---|---|
| Backend completo (`pytest tests/ -q`) | **verde** (exit 0; 725 passed, 5 skipped al commit E3.2, invariato — E3.3 è solo frontend) |
| Frontend completo (`CI=true npm test`) | **123 passed, 14 suite, 3 snapshot** |
| Build (`CI=true npm run build`) | **verde** |

Test dedicati fase E3: `test_archivio_search.py` (13, di cui 2 PG-only skip su
SQLite), `test_archivio_chiedi.py` (13). Le regole di onestà hanno un test
esplicito ciascuna.

## 2. RBAC — lettura archivio per i 3 ruoli (DB reale, RBAC_ENFORCE=true)

Verifica via `TestClient` sull'app reale (route fresche) puntata al DB reale,
token JWT reali per gli utenti `ui_test_*`, middleware RBAC attivo.

| Endpoint | admin | operatore | consultazione |
|---|---|---|---|
| `GET /api/v1/archivio/search` | 200 | 200 | 200 |
| `POST /api/v1/archivio/chiedi` | 200 | 200 | 200 |

`/api/v1/archivio` è in `OPERATIONAL_PREFIXES` (GET = 3 ruoli); `POST /chiedi`
è in `ARCHIVIO_QUERY_PATHS` (query di lettura, valutata prima del blocco
operational → 3 ruoli). Mirror in `frontend/src/auth/permissions.js`.

## 3. Onestà — stati reali (dimostrati empiricamente)

**Sul DB reale (corpus vuoto, NEW-036):** ogni `POST /chiedi` →
`stato="non_presente"`, `risposta=None`, **LLM mai chiamato** (il retrieval
vuoto corto-circuita prima dell'LLM). Regola (a) verificata su dati veri.

**Su clone seedato** (`gestionale_e3gate`, corpus realistico: 10 regole
validate + 3 conoscenze + 2 esiti su formazienda/fondimpresa/fapi):

| Scenario | Stato | Note |
|---|---|---|
| retrieval pieno + LLM ok, citazione valida | `ok` | 1 citazione (`regola:10`), risposta ancorata ai passaggi |
| retrieval pieno + LLM giù (RuntimeError) | `degradato` | `risposta=None`, 2 risultati di ricerca comunque restituiti; LLM invocato e fallito con degrado pulito |
| retrieval pieno + LLM cita id fuori retrieval (`regola:999999`) | `degradato` | risposta scartata server-side, warning loggato |
| retrieval vuoto | `non_presente` | LLM mai chiamato |

La ricerca funziona sempre; l'LLM è un layer sopra, mai una dipendenza dura.

## 4. Verifica empirica FTS — 10 query d'ufficio (clone seedato)

| Query | n risultati | fonte top / articolo | rank | pertinente |
|---|---|---|---|---|
| massimale orario docenza | 2 | regola / Art. 15 | 0.501 | sì |
| spese ammissibili tutoraggio | 1 | conoscenza | 0.264 | sì |
| scadenza presentazione domanda | 2 | regola / Art. 5 | 0.430 | sì |
| cofinanziamento privato | 1 | regola / Art. 8 | 0.271 | sì |
| rendicontazione a costi reali | 2 | regola / Art. 20 | 0.819 | sì |
| IVA ammissibile | 1 | regola / Art. 21 | 0.280 | sì |
| massimale coordinamento | 2 | regola / Art. 13 | 0.134 | sì |
| documentazione obbligatoria collaboratori | 1 | regola / Art. 22 | 0.487 | sì |
| parametri costo formazione | 1 | conoscenza | 0.344 | sì |
| vincolo macrovoce gestione | 1 | regola / Art. 9 | 0.448 | sì |

**10/10 pertinenti** quando il lessico della query è presente (anche flesso:
lo stemming `italian` matcha "presentata"←"presentazione"). L'ordinamento per
`ts_rank` privilegia i match densi ("rendicontazione a costi reali" 0.819).

## 5. Limite di recall e raccomandazione pgvector

La FTS è **lessicale**: non trova sinonimi né riformulazioni. Su 4 query
sinonimiche il cui concetto È nel corpus:

| Query (sinonimo) | Concetto presente come | Esito |
|---|---|---|
| "compenso formatori" | massimale **docenza** | 0 risultati (MISS) |
| "termine ultimo istanza" | **scadenza** presentazione | 0 risultati (MISS) |
| "quota a carico azienda" | **cofinanziamento** privato | 0 risultati (MISS) |
| "imposta sul valore aggiunto" | **IVA** (sigla) | 0 risultati (MISS) |

**4/4 MISS.** Per la ricerca inter-fondo, dove enti diversi usano lessici
diversi per lo stesso concetto (docente/formatore/tutor d'aula, ente
attuatore/soggetto beneficiario), la FTS lessicale è insufficiente.

**RACCOMANDAZIONE: riaprire pgvector** (ricerca semantica per embedding)
quando arriverà corpus reale sufficiente a giustificarla. **NON implementato
ora** — sarebbe prematuro con le fonti vuote (NEW-036) e senza un volume reale
su cui misurare il guadagno. La FTS attuale resta la base corretta e portabile
(fallback ILIKE su SQLite = anche degrado runtime).

## 6. Stato NEW-036 (corpus vuoto in produzione)

Le 3 fonti (`avviso_regole`, `avviso_conoscenze`, `avviso_esiti_progetto`)
sono **vuote sul DB reale** (0/0/0). La feature "Chiedi all'archivio" è
**pronta e corretta ma inerte** finché la pipeline di ingestione avvisi (V2)
non produce regole validate e conoscenze. Non è un difetto della fase E3: il
motore, gli endpoint, la UI e l'enforcement dell'onestà sono dimostrati sul
clone. La verifica di recall su dati veri va rifatta dopo la prima ingestione
reale (è anche il banco di prova dei sinonimi di chiave dei massimali, E1.4).

## 7. Integrità DB reale e teardown

- DB reale `gestionale` invariato prima/dopo: fonti 0/0/0, piani 4. Nessuna
  scrittura sul reale in tutta la verifica.
- Clone `gestionale_e3gate` creato, seedato, interrogato e **droppato**.
- `/health` reale → 200.

## 8. Dichiarazione di chiusura fase E3

**FASE E3 CHIUSA** — ricerca FTS, endpoint search/chiedi con onestà non
negoziabile (retrieval vuoto → non_presente senza LLM; citazioni validate
server-side; LLM giù → degrado pulito), UI a 3 ruoli con disclaimer e stati
visibili. Migration 061 su DB reale. Suite verdi. Unica riserva onesta:
NEW-036 (corpus di produzione vuoto) — la feature attende dati reali;
raccomandazione pgvector riaperta per il recall semantico inter-fondo, da
valutare a corpus popolato.
