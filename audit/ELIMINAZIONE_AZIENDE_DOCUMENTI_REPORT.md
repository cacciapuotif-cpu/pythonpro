# Report eliminazione aziende e documenti

Data: 31/07/2026  
Branch: `claude/platform-audit-compliance-XnH86` (locale, nessun push)

## Diagnosi iniziale

- Aziende: esisteva solo `DELETE /api/v1/aziende-clienti/{azienda_id}` per la disattivazione; nessun endpoint `/permanent`, nessun servizio hard-delete e nessun pulsante UI.
- Documenti progetto: nessun endpoint DELETE, nessun servizio e la UI esponeva solo “Scarica”.
- La catena si interrompeva ai gate di matrice: era stato realizzato il pattern di cancellazione avvisi, ma non quello per aziende/documenti.

## Implementazione

- `fix(DEL-01): implement company hard deletion` (`a22e381`): impatto/cancellabilità, RBAC ADMIN, doppia conferma, audit `azienda_hard_delete`, chiusura suggerimenti agenti, bulk parziale.
- `fix(DOC-01): implement document delete and archive` (`52dc15f`): impatto, hard-delete/archiviazione, RBAC, motivo obbligatorio, audit, ripristino versione precedente, rimozione file fisico e marcatura `fonte_rimossa`.
- `fix(DEL-01): expose company hard delete controls` (`9f2f9b3`): pulsanti UI ADMIN e flusso di conferma.
- `fix(DOC-01): restore previous document version` (`03cb9fe`): versione precedente nuovamente corrente dopo eliminazione.
- Migration Alembic `069_document_deletion_metadata`, provata su copia con downgrade/upgrade e applicata al DB reale.

## Prova su DB copia

- Azienda isolata: impatto 200; eliminazione 200; record assente; audit presente.
- Azienda collegata (id 10): impatto non eliminabile; hard-delete 409 con elenco (`allievi=4`, `sedi=1`, `azienda_cliente_projects=1`).
- Operatore su hard-delete azienda: 403.
- Documento su bozza: DELETE 200; record rimosso; file fisico rimosso; audit `project_document_hard_delete` presente.
- Documento su piano `inviato`: DELETE 409; archiviazione 200 con stato `annullato` e motivo.

Backup usato: `/DATA/progetti/pythonpro_backup_pre_del_doc_20260731_120500.sql.gz`  
SHA-256: `94dd7dc2efc0fa4260ce7423d55961b21e2ce477a6c3be03cf566fa4128a6c59`.

## Verifiche

- Frontend: 40 suite, 325 test, 0 fallimenti.
- Backend: **986 passed, 6 skipped, 0 failed** (33 warning di deprecazione non bloccanti).
- Immagini backend/frontend ricostruite esplicitamente e container ricreati; migration reale a `069`.

Il DB copia e i file temporanei usati dalla prova sono stati rimossi dopo la
verifica. Le prove sono state eseguite prima della pulizia, quindi non hanno
modificato il DB reale.

## Esito

**ELIMINAZIONE AZIENDE FUNZIONANTE: SÌ**  
**ELIMINAZIONE DOCUMENTI FUNZIONANTE: SÌ**
