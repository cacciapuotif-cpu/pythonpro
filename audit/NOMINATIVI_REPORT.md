# Convenzione nominativi — 31/07/2026

## Regola applicata

`formatPersonName` restituisce sempre `COGNOME Nome`; `comparePeople` ordina
per cognome e nome con normalizzazione Unicode e confronto italiano
case/accent-insensitive. Sul server la stessa regola usa `lower(unaccent())`
prima di offset/limit, quindi ricerca e paginazione restano coerenti.

## Punti migrati

- Timesheet, calendario e filtro collaboratori.
- Presenze, assegnazioni e tabella collaboratori.
- Allievi, albero progetto e gestione associati.
- Aziende (referenti), consulenti e preventivi.
- Dashboard, utenti, documenti mancanti e proposte agenti.
- Fallback dei documenti generati (contratti) per il nominativo collaboratore.

Query server aggiornate: collaboratori, collaboratori con progetti, allievi,
consulenti e lista collaboratori filtrata. Migration Alembic `070` crea
extension `unaccent`, funzione immutabile e indici funzionali per le tre
anagrafiche.

## Censimento dati reale

Sono presenti capitalizzazioni anomale legittime/storiche (nomi in maiuscolo),
tra cui `FELICE RUSSILLO`, `DOMENICO CILENTO` e altri record anagrafici; è
presente anche il record di prova `Codex Runtime Test` (id 33). Gli allievi
sono analogamente memorizzati in maiuscolo. Nessuna normalizzazione dati è
stata eseguita: l'ordinamento funziona sui valori esistenti.

## Verifiche

- Frontend: **41 suite, 327 test, 0 fallimenti**.
- Backend mirato: **27 passed**; suite completa: **986 passed, 6 skipped, 0 failed**.
- Migration 069→070 provata su DB copia con downgrade/upgrade e applicata al
  DB reale (versione `070`).
- Backup pre-migration: `/tmp/pre_person_order_20260731.dump`, SHA-256
  `f27f2a55b0b0a13815c3cc9ab3b6a006e385723a09bbaaf6d0c67b4fe2700471`.
