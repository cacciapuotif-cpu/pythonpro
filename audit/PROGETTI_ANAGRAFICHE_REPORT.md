# Ondata Correzioni Progetti e Anagrafiche — GATE PRJ-5

**Data censimento:** 2026-07-31  
**Modalità:** sola lettura sul DB reale; nessuna correzione dati eseguita.  
**Backup pre-gate:** `/DATA/progetti/pythonpro_backup_pre_prj5_20260731_093201.sql.gz`  
**SHA-256:** `30b8c85f93689cd98fc4460256c5b3959af18632d831d87efcd75e8243deb75c`

## Diagnosi della catena di assegnazione avviso

Il parser FAPI (`backend/services/parsers/fapi/convenzione_parser.py`) estrae
codice piano, delibera, importi, ente attuatore e allegati, ma **non estrae
numero/anno dell'avviso**. Anche `_estratti_progetto()` in
`backend/routers/convenzione_upload.py` non trasferisce alcun campo avviso.
I due endpoint di conferma convenzione quindi non possono ricavare o collegare
l'avviso dal PDF.

Il percorso CRUD corrente (`_resolve_project_financial_refs` in `backend/crud.py`)
risolve solo `avviso_id` indicato esplicitamente o codice avviso esatto
(`Avviso.codice`), eventualmente filtrato per ente. Non è presente un fallback
al primo avviso attivo dello stesso fondo. Il dato sbagliato di MAXI è invece
riconducibile alla bonifica storica `scripts/bonifiche/2026-07-17_new010_bonifica.sql`,
che assegnava esplicitamente progetto 11 e piano 7 a FAPI 2/2025 (ID 6). La
bonifica verificava solo la coerenza FK/fondo, non il contenuto della
convenzione.

La UI `ProjectManager` conserva campi `avviso`/`avviso_id` nello stato e nel
payload, ma non mostra un controllo editabile dell'avviso: l'operatore non ha
oggi un percorso trasparente per correggere il collegamento.

## Censimento live

| Progetto | Avviso assegnato | Documento disponibile | Avviso dichiarato dal documento | Esito |
|---:|---|---|---|---|
| #5 `poppi` | FAPI 4/2025 (ID 5, rev. 5) | nessun `convenzione_file_path`, nessun `project_documents` | non verificabile | nessuna correzione proposta |
| #11 `MAXI COMMUNICATION` | FAPI 2/2025 (ID 6, rev. 6); piano #7 agganciato allo stesso avviso | 2 PDF `convenzione` (versioni 1 e 2) | **FAPI Avviso 6-2025**, codice piano `20250611CMIA001` | **disallineamento certo** |

Entrambi i PDF di #11 riportano nella prima pagina e nell'art. 1:
`Avviso 6-2025`, `Cod. Piano: 20250611CMIA001`, FAPI, delibera n. 7 del
24/03/2026. Il database non contiene attualmente un record `avvisi` per
`fondo=fapi, numero=6, anno=2025`: non è quindi possibile correggere la FK
creando un collegamento verso un record già esistente.

## Query di verifica ripetibile

```sql
SELECT p.id, p.name, p.avviso_id, p.avviso_revisione_id, p.avviso,
       a.codice, a.fondo, a.numero, a.anno,
       p.convenzione_file_path
FROM projects p
LEFT JOIN avvisi a ON a.id = p.avviso_id
WHERE p.avviso_id IS NOT NULL
ORDER BY p.id;

SELECT p.id AS project_id, p.name, pd.versione, pd.file_path, pd.file_name
FROM projects p
JOIN project_documents pd ON pd.project_id = p.id
WHERE pd.tipo_documento IN ('convenzione', 'atto_concessione', 'delibera')
ORDER BY p.id, pd.versione;

SELECT id, codice, fondo, numero, anno, revisione_corrente_id
FROM avvisi
WHERE fondo = 'fapi' AND numero = '6' AND anno = 2025;
```

## Correzione proposta — NON ESEGUITA

La correzione deve essere preceduta dall'ingestione ufficiale dell'Avviso FAPI
6/2025 (con fonte e revisione), non dalla creazione di un record sintetico.
Dopo l'ingestione, sostituire i placeholder con gli ID realmente creati e
presentare nuovamente il diff all'utente:

```sql
-- PRJ-5: proposta per conferma esplicita dell'utente, non eseguire ora.
BEGIN;

-- :avviso_fapi_6_2025_id e :revisione_fapi_6_2025_id devono appartenere
-- allo stesso Avviso ufficiale appena ingestito.
UPDATE projects
SET avviso_id = :avviso_fapi_6_2025_id,
    avviso_revisione_id = :revisione_fapi_6_2025_id,
    avviso = '6/2025',
    updated_at = now()
WHERE id = 11;

UPDATE piani_finanziari
SET avviso_pf_id = :avviso_fapi_6_2025_id,
    avviso_revisione_id = :revisione_fapi_6_2025_id,
    updated_at = now()
WHERE id = 7 AND progetto_id = 11;

SELECT p.id, p.avviso_id, p.avviso_revisione_id, p.avviso,
       pf.id AS piano_id, pf.avviso_pf_id, pf.avviso_revisione_id
FROM projects p
LEFT JOIN piani_finanziari pf ON pf.progetto_id = p.id
WHERE p.id = 11;

-- COMMIT solo dopo verifica dei risultati e conferma progetto per progetto.
ROLLBACK;
```

## Gate PRJ-5

Richiesta decisione utente:

1. confermare la correzione di progetto #11 e piano #7 verso l'Avviso FAPI
   6/2025, dopo ingestione della fonte ufficiale;
2. confermare che #5 `poppi` resti invariato in assenza del documento;
3. autorizzare l'implementazione del fix applicativo: estrazione avviso
   esplicita, nessun fallback, stato “non riconosciuto”/selezione obbligatoria,
   alert di mismatch e modifica auditata dalla scheda progetto.

Fino a queste conferme non vengono modificati né `projects` né
`piani_finanziari`.
