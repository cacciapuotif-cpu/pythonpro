# Attività Predittive — Sottosistema A — Implementation Plan

> **For agentic workers:** eseguire un task alla volta. Ogni task è indipendente,
> TDD e termina con un commit locale atomico. Mai push.

**Goal:** materializzare, con approvazione umana, checklist operative per progetto
da scadenze/regole validate e playbook versionati, mantenendo un event log
append-only per il futuro sottosistema B.

**Architecture:** cinque modelli SQLAlchemy in migration `058`; servizi di dominio
senza HTTP; due collector proposal-only (uno deterministico, uno LLM mockabile);
persistenza degli agenti esclusivamente tramite `run_agent_workflow`; apply umano
tramite `suggestion_apply`; router protetto con RBAC.

## Global Constraints

- Mai push. Solo commit locali `feat(ATT-NN): ...`.
- Collector puri: zero scritture DB. La sola persistenza agente è
  `run_agent_workflow`; la materializzazione richiede `user_id` autenticato e
  apply umano.
- Codice nuovo nei servizi di dominio; nessuna funzione in `backend/crud.py` root.
- Migration solo Alembic, provata su copia DB; `058` dipende da `057`.
- TDD per ogni task: test rosso, implementazione minima completa, test verde,
  commit. Nessuna chiamata LLM reale nei test.
- Suite completa verde alla fine dell’ondata; mantenere intatta la worktree
  preesistente e usare staging selettivo.
- Nessun cron MVP: gli agenti si avviano solo manualmente.
- Comandi standard: `docker compose exec -T backend python -m pytest ... -v`;
  output atteso esplicitato sotto ogni task.

## File Structure

| File | Responsabilità |
|---|---|
| `backend/models.py` | `Playbook`, `PlaybookVersione`, `PlaybookVoce`, `AttivitaOperativa`, `AttivitaEvento` |
| `backend/alembic/versions/058_attivita_predittive.py` | schema DB e indici |
| `backend/schemas_attivita.py` | enum, union contenuto e request/response Pydantic |
| `backend/services/playbook.py` | versionamento, review, query operative, apply voce |
| `backend/services/attivita.py` | apply piano, state machine, mutazioni ed eventi |
| `backend/ai_agents/activity_planner.py` | collector deterministico |
| `backend/ai_agents/procedure_extractor.py` | collector LLM |
| `backend/ai_agents/prompts/procedure_extractor_v1.py` | prompt versionato |
| `backend/ai_agents/llm_schemas.py` | schemi output procedura |
| `backend/ai_agents/__init__.py` | wrapper e registry agenti |
| `backend/services/suggestion_apply.py` | dispatch dei due nuovi kind |
| `backend/routers/attivita.py` | API checklist/playbook e RBAC |
| `backend/main.py` | registrazione router |
| `backend/tests/test_attivita_models.py` + `test_playbook_service.py` + `test_attivita_service.py` + `test_activity_planner.py` + `test_procedure_extractor.py` + `test_attivita_router.py` | gate TDD |

---

## Task 1: Modelli, migration 058 e vincoli DB (ATT-01)

**Files:**
- Modify: `backend/models.py`
- Create: `backend/alembic/versions/058_attivita_predittive.py`
- Create: `backend/tests/test_attivita_models.py`

**Interfaces:** cinque modelli con i campi/vincoli della spec; relazioni ciclo
`Playbook.versione_corrente_id`/`PlaybookVersione.playbook_id` con `use_alter`;
JSON sempre `AVVISO_JSON_TYPE`; nomi `ck_`, `uq_`, `ix_`, `fk_` identici fra
modello e migration.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_attivita_models.py
from datetime import datetime
from pathlib import Path
import sys
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))
from database import Base
from models import (AttivitaEvento, AttivitaOperativa, Playbook, PlaybookVersione,
                    PlaybookVoce, Project, User)


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'attivita.db'}")
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        yield session
        session.rollback()
    engine.dispose()


def user(db, role="admin"):
    value = User(username=f"u-{role}", email=f"{role}@example.test",
                 hashed_password="not-used", role=role, is_active=True)
    db.add(value); db.flush(); return value


def test_tables_and_relationship_cycle_exist(db):
    actor = user(db)
    playbook = Playbook(nome="P", fondo="fapi", is_active=True)
    db.add(playbook); db.flush()
    version = PlaybookVersione(playbook_id=playbook.id, numero_versione=1,
                               created_by_user_id=actor.id)
    db.add(version); db.flush()
    playbook.versione_corrente_id = version.id
    db.commit()
    assert playbook.versione_corrente.id == version.id


def test_invalid_phase_and_empty_title_are_rejected(db):
    actor = user(db); p = Playbook(nome="P", fondo="fapi"); db.add(p); db.flush()
    v = PlaybookVersione(playbook_id=p.id, numero_versione=1,
                         created_by_user_id=actor.id); db.add(v); db.flush()
    db.add(PlaybookVoce(playbook_versione_id=v.id, fase="nope", ordine=0,
                        titolo="", contenuto={"tipo":"attivita_semplice"}))
    with pytest.raises(IntegrityError): db.commit()


def test_completion_and_event_actor_checks_are_enforced(db):
    actor = user(db); project = Project(name="P"); db.add(project); db.flush()
    activity = AttivitaOperativa(project_id=project.id, fase="avvio", ordine=1,
        titolo="T", stato="completata", created_by_user_id=actor.id)
    db.add(activity)
    with pytest.raises(IntegrityError): db.commit()
    db.rollback()
    db.add(AttivitaEvento(attivita_id=activity.id, tipo_evento="creata",
                          payload={}, actor_user_id=None, actor_agente=None,
                          created_at=datetime.utcnow()))
    with pytest.raises(IntegrityError): db.commit()


def test_activity_title_unique_per_project_and_phase(db):
    actor = user(db); project = Project(name="P"); db.add(project); db.flush()
    for phase in ("avvio", "avvio"):
        db.add(AttivitaOperativa(project_id=project.id, fase=phase, titolo="T",
                                 ordine=0, created_by_user_id=actor.id))
    with pytest.raises(IntegrityError): db.commit()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T backend python -m pytest tests/test_attivita_models.py -v`

Expected: FAIL con import dei cinque modelli assenti (o tabelle/constraint non
presenti), prima di modificare il modello.

- [ ] **Step 3: Write the implementation**

In `models.py` aggiungere le cinque classi SQLAlchemy con tutti i campi della
spec, `CheckConstraint` nominati, `UniqueConstraint` nominati e indici su
progetto/fase/scadenza/evento. Usare `AVVISO_JSON_TYPE` per `contenuto`,
`applicabilita` e `payload`; impostare `default=datetime.utcnow` per i timestamp.
Definire `Playbook.versione_corrente` con `ForeignKey("playbook_versioni.id",
ondelete="SET NULL", use_alter=True)`, `post_update=True`, e il self-reference
di `PlaybookVersione`/`PlaybookVoce` con `remote_side`.

Creare `058_attivita_predittive.py` con `revision="058"`, `down_revision="057"`.
Eseguire `op.create_table` per `playbooks`, `playbook_versioni`, `playbook_voci`,
`attivita_operative`, `attivita_eventi`, poi `op.create_foreign_key` per il ciclo
`playbooks.versione_corrente_id`; creare gli indici espliciti. `downgrade()` deve
eliminare prima eventi, attività, voci, versioni, la FK ciclica e infine playbook.

- [ ] **Step 4: Run tests and migration gate**

Run:

```bash
docker compose exec -T backend python -m pytest tests/test_attivita_models.py -v
docker compose exec -T backend alembic upgrade 058
docker compose exec -T backend alembic check
```

Expected: 4 PASS; upgrade su copia DB completa; `alembic check` senza drift.

- [ ] **Step 5: Commit**

```bash
git add backend/models.py backend/alembic/versions/058_attivita_predittive.py backend/tests/test_attivita_models.py
git commit -m "feat(ATT-01): modelli e migration attività predittive"
```

---

## Task 2: Schemi Pydantic e servizio playbook (ATT-02)

**Files:**
- Create: `backend/schemas_attivita.py`, `backend/services/playbook.py`
- Create: `backend/tests/test_playbook_service.py`

**Interfaces:** enum `FaseAttivita`, `StatoAttivita`, union discriminata
`VoceContenuto` (`attivita_semplice`, `scadenza_relativa`, `documento`), schemi
create/read; `create_playbook`, `create_next_version`, `add_voce_manuale`,
`review_voce`, `get_playbook_operativo`, `apply_voce_suggestion`.

- [ ] **Step 1: Write the failing tests**

```python
def test_create_playbook_creates_version_one(db, admin):
    from services.playbook import create_playbook
    p = create_playbook(db, nome="FAPI base", fondo="fapi", ente_erogatore=None,
                        descrizione=None, created_by_user_id=admin.id)
    assert p.versione_corrente.numero_versione == 1

def test_new_version_carries_only_validated_voices(db, playbook, admin):
    from services.playbook import add_voce_manuale, create_next_version
    add_voce_manuale(db, versione_id=playbook.versione_corrente_id, fase="avvio",
                     ordine=1, titolo="Valida", contenuto={"tipo":"attivita_semplice"},
                     created_by_user_id=admin.id)
    v2 = create_next_version(db, playbook_id=playbook.id, note="v2",
                             created_by_user_id=admin.id)
    assert [v.titolo for v in v2.voci] == ["Valida"]
    assert v2.voci[0].carried_from_voce_id is not None

def test_operativo_returns_exact_entity_then_fondo_fallback(db):
    from services.playbook import get_playbook_operativo
    assert all(v.stato == "validata" for v in get_playbook_operativo(
        db, fondo="fapi", ente_erogatore="INPS"))

def test_invalid_review_and_missing_reviewer_fail(db, proposed):
    from services.playbook import review_voce
    with pytest.raises(ValueError): review_voce(db, voce_id=proposed.id,
        azione="valida", reviewer_user_id=None, nota=None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T backend python -m pytest tests/test_playbook_service.py -v`

Expected: FAIL con `ModuleNotFoundError`/funzioni mancanti.

- [ ] **Step 3: Write the implementation**

Implementare `schemas_attivita.py` con `ConfigDict(extra="forbid", from_attributes=True)`;
validare titoli non vuoti, confidence 0..1 e `VoceContenuto` tramite
`Annotated[Union[...], Field(discriminator="tipo")]`.

In `services/playbook.py`, usare transazioni SQLAlchemy e `_flush_integrity`:
`create_playbook` crea identità e versione 1; `create_next_version` blocca il
playbook con `with_for_update()`, calcola `max(numero_versione)+1`, copia le sole
voci `validata` valorizzando `carried_from_voce_id`, aggiorna la versione corrente;
`add_voce_manuale` crea voce validata con reviewer e timestamp; `review_voce`
permette solo proposta→validata/rifiutata e richiede reviewer per validazione;
`get_playbook_operativo` sceglie match fondo+ente prima del fallback fondo e
restituisce solo voci validate della versione corrente. `apply_voce_suggestion`
risolve/crea playbook e versione solo durante apply umano, quindi crea la voce
validata con `origin_suggestion_id` e `validata_da_user_id`.

- [ ] **Step 4: Run tests**

Run: `docker compose exec -T backend python -m pytest tests/test_playbook_service.py -v`

Expected: 4 PASS (incluse versioning/carry-forward, fallback e review fail-closed).

- [ ] **Step 5: Commit**

```bash
git add backend/schemas_attivita.py backend/services/playbook.py backend/tests/test_playbook_service.py
git commit -m "feat(ATT-02): schemi e servizio playbook versionato"
```

---

## Task 3: Servizio attività, state machine ed eventi (ATT-03)

**Files:**
- Create: `backend/services/attivita.py`
- Create: `backend/tests/test_attivita_service.py`

**Interfaces:** `ATTIVITA_STATE_TRANSITIONS`; `apply_piano_attivita`,
`cambia_stato`, `aggiorna_attivita`, `lista_attivita`.

- [ ] **Step 1: Write the failing tests**

```python
def test_state_machine_writes_completion_and_event(db, activity, operator):
    from services.attivita import cambia_stato
    cambia_stato(db, attivita_id=activity.id, nuovo_stato="completata",
                 user_id=operator.id, nota="ok")
    db.refresh(activity)
    assert activity.stato == "completata" and activity.completata_da_user_id == operator.id
    assert [e.tipo_evento for e in activity.eventi][-1] == "stato_cambiato"

def test_invalid_transition_returns_domain_error(db, completed, operator):
    from services.attivita import cambia_stato
    with pytest.raises(ValueError, match="Transizione"):
        cambia_stato(db, attivita_id=completed.id, nuovo_stato="in_corso",
                     user_id=operator.id)

def test_apply_is_idempotent_and_creates_events(db, suggestion, operator):
    from services.attivita import apply_piano_attivita
    assert apply_piano_attivita(db, suggestion, user_id=operator.id) == {"create": 1, "esistenti": 0}
    assert apply_piano_attivita(db, suggestion, user_id=operator.id) == {"create": 0, "esistenti": 1}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T backend python -m pytest tests/test_attivita_service.py -v`

Expected: FAIL perché il servizio non esiste.

- [ ] **Step 3: Write the implementation**

Definire transizioni esplicite: `da_fare`→`in_corso|completata|non_applicabile`,
`in_corso`→`completata|da_fare|non_applicabile`, `completata`→`da_fare`,
`non_applicabile`→`da_fare`. Ogni mutazione deve usare `with_for_update()`,
scrivere l’evento nella stessa transazione e fare `flush` prima del commit.
`cambia_stato` valorizza/azzera completamento; riapertura usa evento `riaperta`.
`aggiorna_attivita` emette gli eventi pertinenti per scadenza, assegnatario e nota.
`apply_piano_attivita` legge `suggestion.auto_fix_payload`, deduplica per
`(project_id,fase,titolo)`, crea attività ed evento `creata`, ritorna i conteggi.
`lista_attivita` ordina fase, ordine, scadenza e non espone proposte.

- [ ] **Step 4: Run tests**

Run: `docker compose exec -T backend python -m pytest tests/test_attivita_service.py -v`

Expected: 3 PASS; nessun evento scritto da collector, transazioni atomiche.

- [ ] **Step 5: Commit**

```bash
git add backend/services/attivita.py backend/tests/test_attivita_service.py
git commit -m "feat(ATT-03): state machine attività ed event log append-only"
```

---

## Task 4: Activity planner, registry e apply piano (ATT-04)

**Files:**
- Create: `backend/ai_agents/activity_planner.py`
- Modify: `backend/ai_agents/__init__.py`, `backend/services/suggestion_apply.py`
- Create: `backend/tests/test_activity_planner.py`

**Interfaces:** `collect_activity_planner_suggestions(db, *, project_id,
input_payload=None)`; wrapper `_run_activity_planner`; kind
`ATTIVITA_PIANO_KIND="attivita_piano"`.

- [ ] **Step 1: Write the failing tests**

```python
def test_planner_maps_validated_deadlines_and_playbook(db, project):
    from ai_agents.activity_planner import collect_activity_planner_suggestions
    before = db.query(AgentSuggestion).count()
    result = collect_activity_planner_suggestions(db, project_id=project.id)
    assert db.query(AgentSuggestion).count() == before
    assert len(result["suggestions"]) == 1
    items = result["suggestions"][0]["auto_fix_payload"]["attivita"]
    assert {item["fase"] for item in items} == {"presentazione", "avvio", "gestione", "rendicontazione"}

def test_planner_deduplicates_existing_and_missing_anchor_needs_review(db, project, existing_activity):
    from ai_agents.activity_planner import collect_activity_planner_suggestions
    result = collect_activity_planner_suggestions(db, project_id=project.id)
    assert all(x["titolo"] != existing_activity.titolo for x in
               result["suggestions"][0]["auto_fix_payload"]["attivita"])
    assert any(x.get("needs_review") for x in result["suggestions"][0]["auto_fix_payload"]["attivita"])

def test_planner_without_notice_returns_honest_empty_summary(db, project_without_avviso):
    from ai_agents.activity_planner import collect_activity_planner_suggestions
    result = collect_activity_planner_suggestions(db, project_id=project_without_avviso.id)
    assert result["suggestions"] == [] and "avviso" in result["summary"].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T backend python -m pytest tests/test_activity_planner.py -v`

Expected: FAIL con modulo/registry/apply kind assenti.

- [ ] **Step 3: Write the implementation**

Il collector carica il progetto e risolve la revisione diretta o corrente; legge
solo scadenze `stato="validata"`, mappa i tipi nelle quattro fasi, quindi legge
solo voci validate dal playbook applicabile. Valutare `applicabilita` su fondo ed
ente; risolvere `scadenza_relativa` con data di ancora, marcando `needs_review`
quando manca. Deduplicare internamente e contro attività esistenti. Restituire una
sola suggestion deterministica con `confidence_score=1.0`, `severity="medium"`,
`suggestion_type="piano_attivita"`, `entity_type="project"` e payload kind
`attivita_piano`; zero elementi significa zero suggestion e summary esplicito.

Nel registry aggiungere wrapper, definizione con `agent_env_name`, ruoli
`["admin","manager"]`, trigger `manual`, versione `1.0`, export `__all__`.
In `suggestion_apply.py` aggiungere costante e ramo lazy verso
`services.attivita.apply_piano_attivita`, verificando `user_id` obbligatorio.

- [ ] **Step 4: Run tests**

Run: `docker compose exec -T backend python -m pytest tests/test_activity_planner.py -v`

Expected: 3 PASS; assertion esplicita che il collector non cambia il conteggio
righe; workflow/apply end-to-end passa con una sola chiamata di apply umano.

- [ ] **Step 5: Commit**

```bash
git add backend/ai_agents/activity_planner.py backend/ai_agents/__init__.py backend/services/suggestion_apply.py backend/tests/test_activity_planner.py
git commit -m "feat(ATT-04): activity planner e apply piano attività"
```

---

## Task 5: Procedure extractor, prompt, schemi LLM e apply voce (ATT-05)

**Files:**
- Create: `backend/ai_agents/procedure_extractor.py`, `backend/ai_agents/prompts/procedure_extractor_v1.py`
- Modify: `backend/ai_agents/llm_schemas.py`, `backend/ai_agents/__init__.py`, `backend/services/suggestion_apply.py`
- Create: `backend/tests/test_procedure_extractor.py`

**Interfaces:** `ProcedureVoceLLM`/`ProcedureEstrattoLLM`; collector
`collect_procedure_extractor_suggestions(db, *, documento_id, input_payload=None)`;
kind `PLAYBOOK_VOCE_KIND="playbook_voce"`.

- [ ] **Step 1: Write the failing tests**

```python
def test_extractor_batches_segments_and_drops_invalid_items(db, documento, monkeypatch):
    from ai_agents import procedure_extractor as mod
    def fake(_system, _user):
        return {"voci": [
            {"fase":"avvio", "titolo":"Valida", "tipo_contenuto":"attivita_semplice",
             "descrizione":"x", "confidence":1.2, "testo_originale":"fonte"},
            {"fase":"fase-invalida", "titolo":"Scarta", "tipo_contenuto":"attivita_semplice",
             "confidence":0.5, "testo_originale":"x"}]}
    monkeypatch.setattr(mod, "call_ollama_json", fake)
    result = mod.collect_procedure_extractor_suggestions(db, documento_id=documento.id)
    assert len(result["suggestions"]) == 1
    assert result["suggestions"][0]["confidence_score"] == 1.0

def test_failed_llm_group_is_skipped_and_counted(db, documento, monkeypatch):
    from ai_agents import procedure_extractor as mod
    monkeypatch.setattr(mod, "call_ollama_json", lambda *_: (_ for _ in ()).throw(RuntimeError("timeout")))
    result = mod.collect_procedure_extractor_suggestions(db, documento_id=documento.id)
    assert result["suggestions"] == [] and result["summary"]["gruppi_falliti"] == 1

def test_wrong_document_type_fails_clearly(db, non_procedure_document):
    from ai_agents.procedure_extractor import collect_procedure_extractor_suggestions
    with pytest.raises(ValueError, match="vademecum|manuale"):
        collect_procedure_extractor_suggestions(db, documento_id=non_procedure_document.id)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T backend python -m pytest tests/test_procedure_extractor.py -v`

Expected: FAIL con schema/collector/prompt mancanti.

- [ ] **Step 3: Write the implementation**

In `llm_schemas.py` aggiungere modelli Pydantic con enum fase; `tipo_contenuto`
discriminato; `confidence` clamped in `[0,1]`; `_drop_invalid_items` scarta item
malformati e lascia che una fase fuori enum sollevi `ValueError` intercettato dal
drop. Il prompt v1 deve chiedere esclusivamente JSON conforme, citazione originale
e nessuna invenzione.

Il collector verifica documento vademecum/manuale e `.md`, riusa
`clean_markdown`/`segment_markdown`, raggruppa entro `MAX_PROMPT_CHARS=24000`,
mocka `call_ollama_json` nei test, salta gruppi falliti contando
`gruppi_falliti`, crea una suggestion per voce con `needs_careful_review` sotto
0.75 e payload `playbook_voce`. Non scrivere mai DB.

Registrare wrapper/definizione `procedure_extractor` (manual, admin/manager,
kill-switch, versione 1.0) e aggiungere il ramo apply lazy a
`services.playbook.apply_voce_suggestion`; l’apply risolve/crea playbook e
versione corrente solo con reviewer `user_id`, crea voce `vademecum` validata.

- [ ] **Step 4: Run tests**

Run: `docker compose exec -T backend python -m pytest tests/test_procedure_extractor.py -v`

Expected: 3 PASS; LLM sempre mockato; apply end-to-end crea una voce validata.

- [ ] **Step 5: Commit**

```bash
git add backend/ai_agents/procedure_extractor.py backend/ai_agents/prompts/procedure_extractor_v1.py backend/ai_agents/llm_schemas.py backend/ai_agents/__init__.py backend/services/suggestion_apply.py backend/tests/test_procedure_extractor.py
git commit -m "feat(ATT-05): estrattore procedure e apply playbook voce"
```

---

## Task 6: Router attività, RBAC e registrazione FastAPI (ATT-06)

**Files:**
- Create: `backend/routers/attivita.py`
- Modify: `backend/main.py`
- Create: `backend/tests/test_attivita_router.py`

**Interfaces:** router prefix `/api/v1/attivita`; route playbook dichiarate prima
di `/{attivita_id}*`; dipendenze `require_attivita_write` e
`require_attivita_admin`.

- [ ] **Step 1: Write the failing tests**

```python
def test_consultazione_can_read_but_cannot_change_state(client, overrides, activity):
    overrides.user.role = "consultazione"
    assert client.get(f"/api/v1/attivita/projects/{activity.project_id}").status_code == 200
    assert client.post(f"/api/v1/attivita/{activity.id}/stato",
                        json={"nuovo_stato":"completata"}).status_code == 403

def test_operatore_can_complete_activity(client, overrides, activity):
    overrides.user.role = "operatore"
    response = client.post(f"/api/v1/attivita/{activity.id}/stato",
                           json={"nuovo_stato":"in_corso"})
    assert response.status_code == 200

def test_playbook_mutation_is_admin_only(client, overrides):
    overrides.user.role = "operatore"
    assert client.post("/api/v1/attivita/playbooks",
                       json={"nome":"P", "fondo":"fapi"}).status_code == 403

def test_invalid_transition_maps_to_409(client, overrides, completed):
    overrides.user.role = "operatore"
    assert client.post(f"/api/v1/attivita/{completed.id}/stato",
                       json={"nuovo_stato":"in_corso"}).status_code == 409
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T backend python -m pytest tests/test_attivita_router.py -v`

Expected: FAIL con router non registrato.

- [ ] **Step 3: Write the implementation**

Replicare il pattern dependency di `routers/avvisi.py`: ruoli di scrittura
`admin|manager|operatore`, admin-only per creazione/review/versionamento playbook,
lettura per ogni ruolo autenticato. Implementare GET checklist/eventi, POST stato,
PATCH attività e tutte le route playbook della spec; tradurre `ValueError` in 409/422.
L’identità attore arriva sempre da `get_current_user`, mai dal body. In `main.py`
aggiungere import `attivita` e `include_protected_router(attivita.router)`.

- [ ] **Step 4: Run tests**

Run: `docker compose exec -T backend python -m pytest tests/test_attivita_router.py -v`

Expected: 4 PASS; consultazione read-only, operatore può spuntare, playbook admin-only.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/attivita.py backend/main.py backend/tests/test_attivita_router.py
git commit -m "feat(ATT-06): API attività e playbook con RBAC"
```

---

## Task 7: Gate completo, documentazione e chiusura ondata (ATT-07)

**Files:**
- Modify: `STATUS.md`, `AGENTS_PLATFORM.md`
- Create/update: eventuale report di gate in `audit/`

- [ ] **Step 1: Write the failing gate checks**

```bash
docker compose exec -T backend alembic check
docker compose exec -T backend python -m pytest -q
git diff --check
```

Expected iniziale: suite completa o drift può fallire finché l’integrazione non è
allineata; nessun `git diff --check` deve restare rosso alla fine.

- [ ] **Step 2: Implement/document gate**

Eseguire migration su copia DB, verificare upgrade/downgrade e `alembic check`.
Eseguire i sei file nuovi, poi suite completa. Verificare che i due agenti siano
registrati, che i kill switch default siano documentati, che nessun cron sia stato
aggiunto e che i collector non abbiano scritture DB. Aggiornare `STATUS.md` con
ATT-01…ATT-07, migration 058, test totali, eventuali skip e rischi residui;
aggiornare `AGENTS_PLATFORM.md` con i due agenti, i nuovi kind apply, il flusso
proposal-only e gli endpoint/RBAC.

- [ ] **Step 3: Run final gate**

```bash
docker compose exec -T backend python -m pytest tests/test_attivita_models.py tests/test_playbook_service.py tests/test_attivita_service.py tests/test_activity_planner.py tests/test_procedure_extractor.py tests/test_attivita_router.py -v
docker compose exec -T backend python -m pytest -q
docker compose exec -T backend alembic check
git diff --check
```

Expected: tutti i test verdi, `alembic check` senza drift, diff senza errori.

- [ ] **Step 4: Commit**

```bash
git add STATUS.md AGENTS_PLATFORM.md audit/
git commit -m "feat(ATT-07): chiudi gate sottosistema attività predittive"
```

Non eseguire push. Al termine fermarsi e chiedere conferma prima di implementare
qualsiasi task del piano.
