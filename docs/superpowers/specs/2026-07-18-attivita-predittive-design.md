# Attività Predittive — Sottosistema A: Procedura Operativa Predittiva

_Data: 2026-07-18_

Design del sottosistema A del layer predittivo (decisioni confermate in `STATUS.md`,
sezione "Brainstorming layer predittivo"). Playbook dichiarativo versionato in DB +
motore di istanziazione; agenti proposal-only; apply sempre umano.

---

## Contesto

Cosa esiste già (ricognizione 2026-07-18):

- Piattaforma agenti: registry dichiarativo `backend/ai_agents/__init__.py`
  (`_AGENT_DEFINITIONS`), orchestrazione `backend/agent_workflows.py::run_agent_workflow`
  (unica scrittura DB: `AgentRun` + `AgentSuggestion`), apply umano via
  `backend/services/suggestion_apply.py` (dispatch su `auto_fix_payload["kind"]`),
  kill switch doppio in `ai_agents/control.py`.
- Dati avviso validati V2: `AvvisoRegola` e `AvvisoScadenza` (`backend/models.py:440-549`),
  stati `proposta→validata` con CHECK validazione completa (reviewer + timestamp),
  query operative solo su `stato=="validata"` (`crud_avvisi.get_validated_rules`).
- Pattern versionamento: `Avviso` (identità) → `AvvisoRevisione` (`numero_revisione`
  incrementale, self-ref `revisione_precedente_id`, `revisione_corrente_id` con
  `use_alter`/`post_update`); figli puntano alla versione con `ondelete="RESTRICT"`.
- Vademecum/manuali: `AvvisoDocumento` (`models.py:552-577`) prevede già
  `tipo IN (... 'vademecum','manuale_gestione' ...)`; funzioni pure riusabili
  `services/avviso_ingest.py::clean_markdown` / `segment_markdown`.
- LLM: `ai_agents/llm.py::call_ollama_json` + schemi Pydantic in `ai_agents/llm_schemas.py`
  (pattern `AvvisoEstrazioneLLM._drop_invalid_items`); prompt versionati in
  `ai_agents/prompts/<agente>_v1.py`.

Cosa manca:

- Nessuna checklist operativa per fase legata a progetto/avviso.
- Nessun playbook riusabile di procedure per fondo/ente.
- Nessun job/vista che aggreghi `AvvisoScadenza` in attività operative.
- Nessun event log delle azioni operatore su attività (necessario al sottosistema B).

## Obiettivo

1. Modello `AttivitaOperativa`: checklist per fase
   (`presentazione`/`avvio`/`gestione`/`rendicontazione`) collegata a progetto e
   revisione avviso; l'operatore spunta, ogni azione produce un evento.
2. Playbook dichiarativo versionato in DB (`Playbook` → `PlaybookVersione` →
   `PlaybookVoce`), fonte riusabile di procedure per fondo/ente.
3. Agente `activity_planner` (deterministico, collector puro): da regole+scadenze
   validate e playbook validato propone il piano attività → `AgentSuggestion` →
   apply umano materializza.
4. Agente `procedure_extractor` (LLM, collector puro): da vademecum/manuale `.md`
   propone voci playbook → `AgentSuggestion` → apply umano materializza voce validata.
5. Event log `AttivitaEvento`: ponte verso il sottosistema B (apprendimento).

Scope MVP: tutte le fasi con profondità minima — struttura completa, contenuto cresce.
RAG e apprendimento da storico operatori: fuori scope (sottosistema B / complemento futuro).

---

## Architettura

```
 vademecum/manuale (.md, AvvisoDocumento)          regole+scadenze VALIDATE (V2)
        │                                                   │
        ▼                                                   │
 procedure_extractor (LLM, collector puro)                  │
        │  AgentSuggestion kind=playbook_voce               │
        ▼                                                   │
   APPLY UMANO ──► PlaybookVoce (validata)                  │
                        │                                   │
                        ▼                                   ▼
                 Playbook/Versione ──────► activity_planner (deterministico,
                  (validato)                collector puro, entity=project)
                                                 │  AgentSuggestion kind=attivita_piano
                                                 ▼
                                            APPLY UMANO
                                                 │
                                                 ▼
                                        AttivitaOperativa (per fase)
                                          │ spunta/riassegna/nota (operatore)
                                          ▼
                                        AttivitaEvento (event log → sottosistema B)
```

Regole non negoziabili: i collector non scrivono mai sul DB; ogni esecuzione passa
da `run_agent_workflow`; nessuna materializzazione senza apply umano; le query
operative espongono solo voci/attività non-proposte.

---

## Modello dati

Tipi JSON sempre `AVVISO_JSON_TYPE` (cross-dialect SQLite/PostgreSQL).
Naming vincoli: `ix_`/`uq_`/`ck_`/`fk_` coerente modello↔migration.

### Nuova tabella `playbooks` (identità)

| Campo | Tipo | Vincoli |
|---|---|---|
| id | Integer PK | |
| nome | String(200) NOT NULL | |
| fondo | String(20) NOT NULL default `'altro'` | CHECK `ck_playbooks_fondo` stesso enum FONDI avvisi |
| ente_erogatore | String(100) NULL | idx |
| descrizione | Text NULL | |
| versione_corrente_id | FK → playbook_versioni.id | `ondelete="SET NULL"`, `use_alter`, rel. `post_update` |
| is_active | Boolean NOT NULL default true | |
| created_at / updated_at | DateTime | |

Unicità: `uq_playbooks_identita (fondo, ente_erogatore, nome)`.

### Nuova tabella `playbook_versioni`

| Campo | Tipo | Vincoli |
|---|---|---|
| id | Integer PK | |
| playbook_id | FK → playbooks.id NOT NULL | `ondelete="RESTRICT"` |
| numero_versione | Integer NOT NULL | CHECK > 0; `uq_playbook_versioni_numero (playbook_id, numero_versione)` |
| versione_precedente_id | FK self NULL | `ondelete="SET NULL"`, rel. `remote_side` |
| note | Text NULL | |
| created_by_user_id | FK → users.id NULL | `ondelete="SET NULL"` |
| created_at | DateTime | |

Creazione nuova versione: lock `with_for_update()` sull'identità, `numero = last+1`,
carry-forward delle voci validate (`carried_from_voce_id`), aggiorna
`versione_corrente_id` nella stessa transazione (replica `crud_avvisi.create_next_revision`).

### Nuova tabella `playbook_voci`

| Campo | Tipo | Vincoli |
|---|---|---|
| id | Integer PK | |
| playbook_versione_id | FK NOT NULL | `ondelete="RESTRICT"` |
| fase | String(20) NOT NULL | CHECK `ck_playbook_voci_fase IN ('presentazione','avvio','gestione','rendicontazione')` |
| ordine | Integer NOT NULL default 0 | |
| titolo | String(300) NOT NULL | CHECK non vuoto |
| descrizione | Text NULL | |
| contenuto | JSON NOT NULL | payload dichiarativo tipizzato (v. sotto) |
| schema_version | Integer NOT NULL default 1 | |
| applicabilita | JSON NULL | condizioni (es. `{"fondo":"fapi"}`) |
| origine | String(20) NOT NULL default `'manuale'` | CHECK `IN ('manuale','vademecum','regola')` |
| testo_originale | Text NULL | citazione fonte per origine `vademecum` |
| riferimento_articolo | String(100) NULL | |
| stato | String(20) NOT NULL default `'proposta'` | CHECK `IN ('proposta','validata','rifiutata','superata')` |
| confidence | Numeric(5,4) NULL | CHECK 0-1 |
| needs_careful_review | Boolean NOT NULL default false | |
| origin_suggestion_id | FK → agent_suggestions.id NULL | `ondelete="SET NULL"` |
| carried_from_voce_id | FK self NULL | `ondelete="SET NULL"` |
| validata_da_user_id / validata_il | FK users / DateTime NULL | CHECK `ck_playbook_voci_validazione_completa` (come `ck_avviso_regole_validazione_completa`) |

Unicità: `uq_playbook_voci_titolo (playbook_versione_id, fase, titolo)`.

`contenuto` — Union discriminata su `tipo` (Pydantic, `schemas_attivita.py`),
`schema_version=1`, varianti MVP:

- `{"tipo":"attivita_semplice"}` — solo checklist.
- `{"tipo":"scadenza_relativa","ancora":"presentazione|avvio|chiusura|rendicontazione","offset_giorni":-10}` —
  il motore risolve la data dall'`AvvisoScadenza` validata corrispondente.
- `{"tipo":"documento","tipo_documento":"..."}` — segnaposto ponte B3: NON crea
  `DocumentoRichiesto` in questo sottosistema; l'apply B3 futuro lo consumerà.

### Nuova tabella `attivita_operative`

| Campo | Tipo | Vincoli |
|---|---|---|
| id | Integer PK | |
| project_id | FK → projects.id NOT NULL | `ondelete="RESTRICT"`, idx |
| avviso_revisione_id | FK → avviso_revisioni.id NULL | `ondelete="SET NULL"` |
| playbook_voce_id | FK → playbook_voci.id NULL | `ondelete="SET NULL"` |
| avviso_scadenza_id | FK → avviso_scadenze.id NULL | `ondelete="SET NULL"` |
| fase | String(20) NOT NULL | CHECK stesso enum voci, idx |
| ordine | Integer NOT NULL default 0 | |
| titolo | String(300) NOT NULL | CHECK non vuoto |
| descrizione | Text NULL | |
| stato | String(20) NOT NULL default `'da_fare'` | CHECK `IN ('da_fare','in_corso','completata','non_applicabile')` |
| scadenza | Date NULL | idx |
| tassativa | Boolean NOT NULL default false | |
| assegnatario_user_id | FK users NULL | `ondelete="SET NULL"` |
| origin_suggestion_id | FK agent_suggestions NULL | `ondelete="SET NULL"` |
| completata_da_user_id / completata_il | FK users / DateTime NULL | CHECK `ck_attivita_completamento`: `stato <> 'completata' OR (entrambi NOT NULL)` |
| note | Text NULL | |
| created_by_user_id | FK users NULL | `ondelete="SET NULL"` |
| created_at / updated_at | DateTime | |

Unicità: `uq_attivita_operative_titolo (project_id, fase, titolo)` (idempotenza apply).

State machine (`services/attivita.py`, dict esplicito come `AVVISO_STATE_TRANSITIONS`):
`da_fare → in_corso|completata|non_applicabile`; `in_corso → completata|da_fare|non_applicabile`;
`completata → da_fare` (riapertura); `non_applicabile → da_fare`.

### Nuova tabella `attivita_eventi` (event log, ponte sottosistema B)

| Campo | Tipo | Vincoli |
|---|---|---|
| id | Integer PK | |
| attivita_id | FK → attivita_operative.id NOT NULL | `ondelete="CASCADE"`, idx |
| tipo_evento | String(30) NOT NULL | CHECK `IN ('creata','stato_cambiato','scadenza_modificata','assegnata','nota','riaperta')` |
| payload | JSON NULL | es. `{"da":"da_fare","a":"completata"}` |
| actor_user_id | FK users NULL | `ondelete="SET NULL"` |
| actor_agente | String(50) NULL | CHECK `ck_attivita_eventi_actor`: almeno uno dei due actor NOT NULL |
| created_at | DateTime NOT NULL | idx |

Append-only: nessun UPDATE/DELETE esposto. Ogni mutazione di `AttivitaOperativa`
passa dal servizio di dominio che scrive l'evento nella stessa transazione.

### Migration

`backend/alembic/versions/058_attivita_predittive.py` — `revision="058"`,
`down_revision="057"`. Solo `create_table` + indici (nessun backfill: tabelle nuove).
`downgrade()` completo in ordine inverso. Prova su copia DB con `alembic check` prima
del commit (regola di lavoro).

---

## Componenti

### 1. `backend/services/playbook.py` (servizio di dominio, no HTTP)

- `create_playbook(db, *, nome, fondo, ente_erogatore, descrizione, created_by_user_id)` —
  crea identità + versione 1 nella stessa transazione.
- `create_next_version(db, *, playbook_id, note, created_by_user_id)` — lock,
  `numero+1`, carry-forward voci validate, aggiorna `versione_corrente_id`.
- `add_voce_manuale(db, *, versione_id, ..., created_by_user_id)` — voce `origine='manuale'`,
  stato `validata` diretto (curata da umano) con reviewer+timestamp.
- `review_voce(db, *, voce_id, azione in ('valida','rifiuta'), reviewer_user_id, nota)` —
  transizione `proposta→validata|rifiutata` con CHECK completo.
- `get_playbook_operativo(db, *, fondo, ente_erogatore)` — risolve il playbook
  applicabile (match esatto ente, fallback solo fondo) e ritorna SOLO voci `validata`
  della `versione_corrente`.
- `IntegrityError → ValueError` di dominio (helper stile `crud_avvisi._flush_integrity`).

### 2. `backend/services/attivita.py` (servizio di dominio, no HTTP)

- `apply_piano_attivita(db, suggestion, *, user_id)` — materializza il piano proposto:
  per ogni attività nel payload, skip se esiste (`uq project/fase/titolo`), crea
  `AttivitaOperativa` + evento `creata` (actor_user_id = applicatore). Ritorna
  `{"create": n, "esistenti": m}`.
- `cambia_stato(db, *, attivita_id, nuovo_stato, user_id, nota=None)` — valida
  transizione da state machine, `with_for_update()`, set `completata_da/il` quando
  `completata`, azzeramento alla riapertura, evento `stato_cambiato`/`riaperta`.
- `aggiorna_attivita(db, *, attivita_id, user_id, scadenza=..., assegnatario=..., note=...)` —
  eventi `scadenza_modificata`/`assegnata`/`nota`.
- `lista_attivita(db, *, project_id, fase=None, stato=None)` — vista operativa ordinata
  per fase/ordine/scadenza.
- Identità utente sempre kwarg keyword-only dal router autenticato, mai dal payload.

### 3. `backend/ai_agents/activity_planner.py` (collector puro, deterministico, no LLM)

`collect_activity_planner_suggestions(db, *, project_id, input_payload=None)`:

1. Carica progetto; risolve `avviso_revisione_id` (diretto o via `avviso.revisione_corrente_id`).
   Nessun avviso → summary con motivo, zero suggestion.
2. Legge `AvvisoScadenza` validate della revisione → una attività proposta per scadenza
   (fase = mappa tipo scadenza→fase: `presentazione→presentazione`, `avvio→avvio`,
   `chiusura→gestione`, `rendicontazione→rendicontazione`, `altro→gestione`;
   `tassativa` propagata, `scadenza` = data, `avviso_scadenza_id` riferito).
3. Legge playbook operativo (`get_playbook_operativo` per fondo/ente avviso) → una
   attività per voce validata applicabile (`applicabilita` valutata su fondo/ente);
   `scadenza_relativa` risolta su scadenze validate (ancora mancante → attività senza
   data + flag `needs_review` nel payload).
4. Dedup interno per (fase, titolo); legge attività già esistenti del progetto
   (sola lettura) e le esclude.
5. Output: UNA suggestion (`entity_type="project"`, `suggestion_type="piano_attivita"`,
   `severity="medium"`, `confidence_score=1.0` — deterministico) con
   `auto_fix_available=True`, `auto_fix_payload={"kind":"attivita_piano","project_id":...,
   "attivita":[{fase,ordine,titolo,descrizione,scadenza,tassativa,playbook_voce_id,
   avviso_scadenza_id},...]}`. Payload vuoto → zero suggestion, summary onesto.

### 4. `backend/ai_agents/procedure_extractor.py` (collector puro, LLM)

`collect_procedure_extractor_suggestions(db, *, documento_id, input_payload=None)`:

1. Carica `AvvisoDocumento`; accetta solo `tipo IN ('vademecum','manuale_gestione')`
   e `file_path` `.md` (altri formati → ValueError con messaggio chiaro; conversione
   PDF fuori scope MVP).
2. `clean_markdown` + `segment_markdown` (riuso `services/avviso_ingest.py`, funzioni pure).
3. Per gruppo di segmenti (batch fino a `MAX_PROMPT_CHARS=24000`):
   `call_ollama_json(system_prompt, user_prompt)` con prompt da
   `prompts/procedure_extractor_v1.py`; fallimento gruppo → skip + conteggio
   `gruppi_falliti` (pattern avviso_extractor).
4. Valida con `ProcedureEstrattoLLM` (in `llm_schemas.py`): lista voci
   `{fase, titolo, descrizione, tipo_contenuto, offset_giorni?, ancora?,
   tipo_documento?, testo_originale, riferimento_articolo?, confidence}`;
   `_drop_invalid_items` + clamping confidence; fase fuori enum → scartata.
5. Una suggestion per voce proposta (`entity_type="avviso_documento"`,
   `suggestion_type="playbook_voce"`, `confidence_score` dal LLM,
   `needs_careful_review` se < 0.75) con `auto_fix_available=True`,
   `auto_fix_payload={"kind":"playbook_voce","documento_id":...,
   "playbook_id": input_payload.get("playbook_id"), "voce":{...}}`.
   `playbook_id` assente → risolto all'apply su fondo/ente dell'avviso del documento
   (creazione playbook implicita SOLO all'apply umano, mai dal collector).

### 5. Registry e apply

- `ai_agents/__init__.py`: wrapper `_run_activity_planner` (entity `project`) e
  `_run_procedure_extractor` (entity `avviso_documento`); entry in `_AGENT_DEFINITIONS`
  con `kill_switch_env=agent_env_name(...)`, `allowed_roles` come certification,
  `version="1.0"`, triggers `manual`; export in `__all__`.
- `services/suggestion_apply.py`: `ATTIVITA_PIANO_KIND="attivita_piano"` →
  `services.attivita.apply_piano_attivita`; `PLAYBOOK_VOCE_KIND="playbook_voce"` →
  `services.playbook.apply_voce_suggestion` (crea/risolve playbook+versione corrente,
  crea voce `origine='vademecum'` stato `validata` con reviewer=user_id — replica del
  flusso `apply_avviso_extraction_suggestion`). Entrambe richiedono `user_id`.
- Nessun cron in `arq_worker.py` per l'MVP: trigger solo manuale
  (`POST /api/v1/agents/run`, solo ADMIN) — coerente con "profondità minima".

### 6. `backend/routers/attivita.py` + registrazione `main.py`

`APIRouter(prefix="/api/v1/attivita")` registrato con `include_protected_router`.
Dependency locali: `require_attivita_write` (`{admin, manager, operatore}` — l'operatore
spunta), `require_attivita_admin` (`{admin}` per playbook validate/versioni).
Traduzione `ValueError → HTTPException` 409/422 come `routers/avvisi.py`.

---

## API Endpoints

| Metodo | Path | Descrizione | Ruoli |
|---|---|---|---|
| GET | `/api/v1/attivita/projects/{project_id}` | Checklist progetto (filtri fase/stato) | tutti autenticati |
| POST | `/api/v1/attivita/{id}/stato` | Cambio stato (spunta/riapre) | admin/manager/operatore |
| PATCH | `/api/v1/attivita/{id}` | Scadenza/assegnatario/note | admin/manager/operatore |
| GET | `/api/v1/attivita/{id}/eventi` | Event log attività | tutti autenticati |
| POST | `/api/v1/attivita/playbooks` | Crea playbook (+v1) | admin |
| GET | `/api/v1/attivita/playbooks` | Lista playbook + versione corrente | tutti autenticati |
| GET | `/api/v1/attivita/playbooks/{id}/voci` | Voci versione corrente (stato filtrabile) | tutti autenticati |
| POST | `/api/v1/attivita/playbooks/{id}/voci` | Voce manuale (validata) | admin |
| POST | `/api/v1/attivita/playbooks/voci/{voce_id}/review` | Valida/rifiuta voce proposta | admin |
| POST | `/api/v1/attivita/playbooks/{id}/versioni` | Nuova versione (carry-forward) | admin |

Run agenti e apply suggestion: endpoint generici esistenti di `routers/agents.py`
(nessuna modifica al router agents).

## Schemi Pydantic

`backend/schemas_attivita.py`: base `_Schema` con `ConfigDict(extra="forbid",
from_attributes=True)`; `StrEnum` per fasi/stati; Union discriminata `VoceContenuto`
su `tipo` (`attivita_semplice`/`scadenza_relativa`/`documento`) con `schema_version`;
Read eredita da Create + id/timestamp.

## Variabili d'ambiente

```env
AGENT_ACTIVITY_PLANNER_ENABLED=true      # kill switch per-agente (default true)
AGENT_PROCEDURE_EXTRACTOR_ENABLED=true
# procedure_extractor richiede AI_AGENT_LLM_PROVIDER / AI_AGENT_LLM_MODEL già esistenti
```

## Error handling

| Scenario | Comportamento |
|---|---|
| Progetto senza avviso/revisione | Run completed, 0 suggestion, summary con motivo |
| Nessuna scadenza/voce applicabile | Run completed, 0 suggestion, summary onesto |
| Documento non vademecum/manuale o non `.md` | ValueError → run failed con messaggio chiaro |
| Gruppo LLM fallito (timeout/JSON invalido) | Skip gruppo, `gruppi_falliti` in summary, altri gruppi processati |
| Voce LLM malformata / fase fuori enum | Scartata da `_drop_invalid_items`, non abortisce |
| Ancora `scadenza_relativa` non risolvibile | Attività proposta senza data + `needs_review` |
| Apply su attività già esistente | Skip idempotente (uq project/fase/titolo), conteggiata in `esistenti` |
| Transizione stato non ammessa | ValueError dominio → HTTP 409 |
| Kill switch off | `run_agent_workflow` rifiuta con `disabled_reason` (esistente) |

## Testing

Directory `backend/tests/`, SQLite `tmp_path` + PRAGMA FK ON (pattern `test_avvisi_v1.py`).

- `test_attivita_models.py` — CHECK/unique (fase, completamento, actor evento, uq titolo).
- `test_playbook_service.py` — create/next-version/carry-forward/review; voce validata
  richiede reviewer; `get_playbook_operativo` espone solo validate; fallback ente→fondo.
- `test_attivita_service.py` — state machine (transizioni valide/invalide), eventi
  scritti in stessa transazione, apply idempotente.
- `test_activity_planner.py` — collector puro (nessuna scrittura DB: conteggio righe
  prima/dopo), mappa scadenze→fasi, risoluzione `scadenza_relativa`, dedup con
  esistenti, run via `run_agent_workflow`, apply end-to-end.
- `test_procedure_extractor.py` — LLM mockato via `monkeypatch.setattr(modulo,
  "call_ollama_json", fake)`; drop item invalidi; gruppo fallito; apply crea voce
  validata con reviewer; documento tipo sbagliato → failed.
- `test_attivita_router.py` — RBAC (consultazione read-only, operatore spunta,
  playbook solo admin), 409 su transizione invalida.

Nessuna chiamata LLM reale nei test. Suite completa deve restare verde.

## Riconciliazione con Ondata B e L

- **B3 (checklist documentale)**: la voce playbook `tipo_contenuto="documento"` è il
  ponte dichiarativo; questo sottosistema NON crea `DocumentoRichiesto`. B3 consumerà
  le stesse voci per la proposta checklist documentale. Nessun conflitto: domini
  separati (attività operative vs documenti collaboratore).
- **B1 (scadenze in job/notifiche)**: `AttivitaOperativa.avviso_scadenza_id` collega
  attività e scadenza validata; B1 potrà notificare su entrambe senza rimodellare.
- **Ondata L (apprendimento)**: `AttivitaEvento` è la sorgente eventi per il
  sottosistema B/L (pattern comportamento operatori). Append-only, actor esplicito.

## File da creare/modificare

| File | Azione |
|---|---|
| `backend/models.py` | Aggiungere 5 modelli (Playbook, PlaybookVersione, PlaybookVoce, AttivitaOperativa, AttivitaEvento) |
| `backend/alembic/versions/058_attivita_predittive.py` | Nuova migration |
| `backend/schemas_attivita.py` | Nuovo — schemi Pydantic + Union contenuto |
| `backend/services/playbook.py` | Nuovo — servizio dominio playbook |
| `backend/services/attivita.py` | Nuovo — servizio dominio attività + eventi |
| `backend/ai_agents/activity_planner.py` | Nuovo — collector deterministico |
| `backend/ai_agents/procedure_extractor.py` | Nuovo — collector LLM |
| `backend/ai_agents/prompts/procedure_extractor_v1.py` | Nuovo — prompt versionato |
| `backend/ai_agents/llm_schemas.py` | Aggiungere `ProcedureVoceLLM`/`ProcedureEstrattoLLM` |
| `backend/ai_agents/__init__.py` | Registry: 2 wrapper + 2 definizioni + `__all__` |
| `backend/services/suggestion_apply.py` | 2 nuovi kind nel dispatcher |
| `backend/routers/attivita.py` | Nuovo router |
| `backend/main.py` | Import + `include_protected_router(attivita.router)` |
| `backend/tests/test_attivita_models.py` + 5 file test | Nuovi |

## Sequenza di sviluppo

1. Modelli + migration 058 + test modelli (prova migration su copia DB).
2. Schemi Pydantic + servizio playbook + test.
3. Servizio attività (state machine + eventi) + test.
4. `activity_planner` + registry + apply kind `attivita_piano` + test.
5. `procedure_extractor` + prompt + schemi LLM + apply kind `playbook_voce` + test.
6. Router + RBAC + registrazione main + test router.
7. Suite completa verde; aggiornamento `STATUS.md`, `AGENTS_PLATFORM.md`; commit atomici.
