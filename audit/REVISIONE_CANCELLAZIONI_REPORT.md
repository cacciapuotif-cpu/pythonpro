# Ondata Revisione e Cancellazioni — diagnosi DEL-1

## 2026-07-31 — DEL-1(a), prima del fix

Backup verificato prima della diagnosi: `pythonpro_backup_pre_rev_del_20260731_110138.sql.gz`.
SHA-256: `bb86b9d13027fa93b961a27aacd48829dd35647413ed2512d63c9f129cfdbbd3`.

### Catena verificata

| Punto | Stato reale | Evidenza |
|---|---|---|
| Endpoint hard delete azienda | **Assente** | OpenAPI runtime espone `DELETE /api/v1/aziende-clienti/{azienda_id}` soltanto; `/permanent` restituisce 404 |
| Router/main | Soft delete registrato | `backend/routers/aziende_clienti.py:123-139`, incluso da `main.py:290` tramite `include_protected_router` |
| Servizio applicativo | **Assente** | il router chiama solo `crud.delete_azienda_cliente`, che imposta `attivo=false` e fa commit |
| Matrice cancellabilità | **Non implementata** | nessun impact endpoint, schema di conferma, blocco per collegamenti o anonimizzazione |
| UI/API client | Solo disattivazione | `AziendeClientiManager` mostra esclusivamente “Disattiva”; `apiService.js` espone solo `deleteAziendaCliente` |
| RBAC hard delete | **Assente** | il router è protetto solo dal ruolo globale; non esiste dipendenza ADMIN dedicata per aziende |
| Audit hard delete | **Assente** | nessun `azienda_hard_delete`; il pattern esistente è solo `services/avviso_deletion.py` |

### Prova runtime su DB copia

È stato creato `gestionale_revdel_copy_20260731`, ripristinato dal backup e poi rimosso.
Con token ADMIN generato contro la copia:

- `DELETE /api/v1/aziende-clienti/3/permanent` → **404 Not Found** (`{"detail":"Not Found"}`);
- `DELETE /api/v1/aziende-clienti/3` → **200 OK**, record restituito con `attivo:false`.

Il record #3 (`Azienda 97294390584`) è stato riportato ad `attivo=true` nella copia prima della sua rimozione. Nessun dato reale è stato modificato.

### Censimento collegamenti reale (read-only)

Record senza progetto/allievo/sede/fondo: #3, #4, #11, #12, #13, #14. Record collegati: #1 (1 progetto), #2 (1 progetto + 1 fondo), #10 (1 progetto + 4 allievi + 1 sede). Il conteggio è preliminare: il servizio dovrà estendere la matrice a documenti, ordini/preventivi, piani, interazioni e rendicontazione.

### Risultato gate

La catena si interrompe dopo il soft-delete CRUD: hard-delete azienda non è mai stato implementato (endpoint, servizio, UI, matrice, audit e test mancanti). DEL-1(b) è riproducibile su copia. Nessun fix applicato: attendo il via libera sul perimetro della matrice e sul trattamento degli orfani REV-0 prima di scrivere codice.

## REV-0 — censimento iniziale orfani (sola lettura)

Nel DB reale risultano 178 suggerimenti `pending`; per `avviso_revisione` 54 sono orfani (assistente `avviso_extractor`, `entity_id` nullo dopo la cancellazione), 56 restano validi. Gli `AgentRun` collegati restano presenti e alcuni hanno `entity_id` nullo. Proposta: chiudere gli orfani con stato tracciabile “superato/non più applicabile” e motivo, non cancellarli in silenzio; il gate richiede conferma prima della bonifica.

## 2026-07-31 — Maxi Communication / PG01: diagnosi import documenti e moduli

Il progetto #11 ha due soli record in `project_documents`, entrambi di tipo `convenzione` (v1 senza nome file, v2 `convenzioneAvviso012022_20250611CMIA001.pdf`). I due file fisici esistono nello storage (`335642` e `40344` byte). Non esistono record archiviati per formulario o piano finanziario.

I router `upload-formulario` e `upload-piano-finanziario` salvano il file in storage e usano un preview token, ma nei rispettivi `confirm_*` non chiamano `_archivia_documento` e quindi non creano `ProjectDocumento`. Non esistono inoltre endpoint DELETE dei documenti.

Il formulario è non idempotente: ogni conferma esegue solo `INSERT` dei moduli. Per Maxi sono presenti tre batch da 25 righe, creati il 22/04, 31/07 07:23 e 31/07 11:13. PG01 (`...01`) contiene 9 moduli formativi per 120 ore e 6 propedeutici per 60 ore: tre copie dello stesso set da 3+2 moduli. Il set singolo coerente con il dato fornito dall’utente è 3 moduli formativi (40 ore) + 2 propedeutici (20 ore). La correzione deve conservare un solo batch canonico, rendere l’import idempotente e archiviare formulario/piano come documenti versionati.
