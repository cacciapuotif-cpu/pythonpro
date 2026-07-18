# Gate sottosistema A — attività predittive

Data: 2026-07-18
Esito: SUPERATO

## Perimetro

Chiusura ATT-01…ATT-07: modelli e migration, servizi playbook/checklist,
`activity_planner`, `procedure_extractor`, apply umano, router/RBAC, event log e
documentazione operativa.

## Evidenze test

- Gate mirato su nove file ATT reali: **35 passed**, 0 failed.
- Suite backend completa finale: **568 passed, 3 skipped, 0 failed** su 571 test
  in 825.91 secondi, rieseguita dopo la correzione del bypass RBAC.
- Verifica indipendente del confutatore: **100 passed**, 0 failed sui test mirati
  e nessun blocker residuo dopo la correzione.
- Skip: due test monitor performance legacy non disponibile (NEW-013) e un test
  DOM-21 PostgreSQL-only; nessuno riguarda il sottosistema A.
- `git diff --check`: pulito.

## Migration 058

Clone temporaneo `gestionale_att07_gate` creato dal database reale a 057.

1. Upgrade 057→058 riuscito.
2. Primo `alembic check` ha individuato drift fra indici modello e migration.
3. Modelli allineati agli indici compositi della migration.
4. `alembic check`: `No new upgrade operations detected`.
5. Downgrade 058→057: 0 tabelle ATT residue.
6. Conteggi pre/post invariati: projects=5, users=2, avvisi=6.
7. Re-upgrade: 5/5 tabelle e 5/5 indici attesi presenti; drift zero.

Il clone temporaneo è stato eliminato dopo il gate; il censimento finale conferma
0 database con nome `gestionale_att07_gate`.

Prima della migration reale è stato creato e verificato il backup cifrato:
`/app/backups/gestionale_backup_att07_pre_migration_20260718_112650.sql.zip.gpg`
(`INTEGRITY=True`). Il DB reale è stato portato a `058 (head)`; check senza drift.

## Invarianti e RBAC

- Collector senza scritture applicative; la persistenza passa da
  `run_agent_workflow` in `AgentRun`/`AgentSuggestion`.
- Apply di `attivita_piano` e `playbook_voce` richiede `user_id` umano.
- Nessun cron aggiunto per i due agenti; trigger registry solo `manual`.
- Smoke sulla vera `main.app` con enforcement globale:
  consultazione GET=200/POST=403; operatore stato/PATCH=200 e playbook POST=403;
  admin playbook POST=200.
- `AttivitaEvento` è append-only lato API e ordinato per ID.

## Correzioni emerse dal gate

- Prefisso attività aggiunto alla policy RBAC globale.
- Filtro stato voci playbook implementato e input invalido fail-closed 422.
- Date ISO del planner convertite in `date` durante apply.
- PATCH assegnatario riallineata allo schema `assegnatario_user_id` e protetta da lock.
- Apply procedure crea playbook sul fondo/ente corretto e conserva origine,
  confidence, review flag e suggestion sorgente.
- L'apply generico degli agenti non può aggirare il vincolo admin di
  `playbook_voce`; il dispatcher restituisce inoltre il contratto comune
  `applied`/`skipped` senza errori successivi alla materializzazione.
- Test registry/system-health riallineati ai due nuovi agenti.

## Runtime

Backend e ARQ worker riavviati dopo la migration e risultano healthy. `/health`
risponde 200. Il worker ha ripreso con 0 job falliti; i due agenti ATT non compaiono
nello scheduler ARQ.

## Riserve non bloccanti

- NEW-003, catena Alembic greenfield legacy, resta fuori dal perimetro; il gate è
  stato eseguito correttamente su clone del DB reale corrente.
- Warning Starlette/httpx e HTTP 422 deprecato restano debito di toolchain, senza
  failure o impatto sul gate.
- I rilievi residui su unicità del playbook generico, atomicità apply/audit,
  azzeramento campi PATCH e propagazione del flag di review sono tracciati come
  NEW-014…NEW-017 in `audit/FINDINGS_NUOVI.md`; non invalidano il gate corrente.

## Verdetto indipendente

**VERDETTO: VALIDATO.** Il confutatore ha inizialmente respinto la chiusura per il bypass admin sulla
route generica `apply-fix`. Dopo fix, regressione mirata **59 passed**, verifica
indipendente **100 passed** e suite completa **568 passed**: ATT-01…ATT-07 sono
validati senza blocker residui.
