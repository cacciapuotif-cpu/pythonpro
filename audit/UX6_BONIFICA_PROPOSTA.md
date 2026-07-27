# UX-6 — Bonifica proposta (NON eseguita)

Redatta il 2026-07-27 sul DB reale `gestionale`, con analisi in **sola lettura**.
Backup di riferimento: `/DATA/progetti/pythonpro_backup_pre_ux_20260727.sql`
(1.2 MB, 58 blocchi `COPY`, marker di fine presente, `alembic_version = 063`).

> **Nulla qui è stato eseguito.** Ogni blocco termina con `ROLLBACK`: per
> applicarlo davvero va sostituito con `COMMIT`, e solo dopo conferma esplicita.

## Esito del censimento

Non esistono piani finanziari duplicati: 4 piani su 4 progetti distinti, nessun
piano senza voci, nessun codice FAPI ripetuto. **Il duplicato è a livello di
PROGETTO** — che nel dominio è "il piano" formativo.

| id | nome | ente | codice FAPI | creato | giudizio |
|----|------|------|-------------|--------|----------|
| 11 | MAXI COMMUNICATION | FAPI | `20250611CMIA001` | 2026-04-22 | **buono** |
| 12 | MAXI COMMUNICATION | — | nessuno | 2026-07-27 11:10 | doppione con un dato utile |
| 13 | Piano FAPI | FAPI | nessuno | 2026-07-27 11:15 | fantasma del bug |

Il **12** è una creazione *manuale* dell'operatore (descrizione
`Piano Fapi 20250611CMIA001`, date proprie) e porta un dato che il 11 **non ha**:
il CUP `G64D26000610003`. Non è un rifiuto da buttare.

Il **13** è il fantasma prodotto dal bug: nome di fallback, nessun dato proprio,
solo il PDF dell'atto e 5 link azienda copiati dal 11.

Nessuna presenza, assegnazione, modulo, piano finanziario, ordine o contratto è
agganciato a 12 o 13.

### ⚠️ Interazione con UX-7 — il 12 NON è vuoto

Emersa durante la diagnosi UX-7: il progetto **12 è l'unico che abbia allievi
associati in tutto il sistema**. Sono 4 su 4, tutti di Power Impianti srl.

| tabella | progetto 11 | progetto 12 | progetto 13 |
|---------|-------------|-------------|-------------|
| `azienda_cliente_projects` | 5 | 5 | 5 |
| `allievo_project` | **0** | **4** | 0 |

È coerente col racconto: l'operatore ha creato il 12, vi ha associato le
aziende e gli allievi, e la scheda ha continuato a dire "nessun allievo
associato" — perché l'API non restituiva quel campo (UX-7), non perché il
salvataggio fosse fallito. Poi ha caricato l'atto, generando il 13.

**Eliminare il 12 senza travasare prima gli allievi cancella l'unico dato di
associazione allievi presente in produzione.** Il blocco A lo previene.

## Verifica preliminare — rieseguire prima di qualsiasi scrittura

```sql
SELECT p.id, p.name, p.codice_fapi, p.cup, p.created_at,
       (SELECT count(*) FROM azienda_cliente_projects x WHERE x.project_id = p.id) AS link,
       (SELECT count(*) FROM assignments      x WHERE x.project_id  = p.id) AS assegnazioni,
       (SELECT count(*) FROM attendances      x WHERE x.project_id  = p.id) AS presenze,
       (SELECT count(*) FROM piani_finanziari x WHERE x.progetto_id = p.id) AS piani,
       (SELECT count(*) FROM moduli_formativi x WHERE x.project_id  = p.id) AS moduli,
       (SELECT count(*) FROM ordini           x WHERE x.progetto_id = p.id) AS ordini
FROM projects p WHERE p.id IN (11, 12, 13) ORDER BY p.id;
```

Procedere **solo** se per 12 e 13 assegnazioni, presenze, piani, moduli e ordini
sono tutti a zero.

## Blocco A — travaso dei dati originali dal 12 al progetto buono

Il CUP e le associazioni allievi sono i dati che vivono **solo** sul 12.
`NULLIF/TRIM` fa sì che il CUP del 11 non venga toccato se già valorizzato;
il `NOT EXISTS` rende il travaso degli allievi ripetibile senza duplicare.

```sql
BEGIN;

-- 1. il CUP
UPDATE projects
SET cup = (SELECT cup FROM projects WHERE id = 12)
WHERE id = 11 AND NULLIF(TRIM(COALESCE(cup, '')), '') IS NULL;

-- 2. i 4 allievi associati (unici in tutto il sistema), con il loro stato
INSERT INTO allievo_project
       (allievo_id, project_id, ore_frequentate, stato, attestato_emesso, note)
SELECT ap.allievo_id, 11, ap.ore_frequentate, ap.stato, ap.attestato_emesso, ap.note
FROM allievo_project ap
WHERE ap.project_id = 12
  AND NOT EXISTS (
      SELECT 1 FROM allievo_project x
      WHERE x.allievo_id = ap.allievo_id AND x.project_id = 11
  );

SELECT (SELECT cup FROM projects WHERE id = 11) AS cup_11,
       (SELECT count(*) FROM allievo_project WHERE project_id = 11) AS allievi_11;
-- atteso: cup_11 = G64D26000610003, allievi_11 = 4
ROLLBACK;  -- -> COMMIT per applicare
```

Colonne di `allievo_project` verificate: `ore_frequentate`, `stato`,
`attestato_emesso` e `note` viaggiano insieme alla coppia di FK, così lo stato
di iscrizione non si azzera nel travaso. La PK è `(allievo_id, project_id)`.

> **Perché il blocco A non è opzionale.** `allievo_project.project_id` ha
> `ON DELETE CASCADE`: un `DELETE FROM projects WHERE id = 12` porta via le 4
> righe **senza errore e senza avviso**. Eseguire il blocco C da solo
> cancellerebbe in silenzio l'unico dato di associazione allievi in produzione.

**Non travasate le date.** Quelle del 12 (2026-04-21 → 2027-02-16) confliggono
con quelle del 11 (2026-04-23 → 2026-06-09). Quale sia la buona è una domanda di
dominio e si incrocia con UX-5 (semantica delle date di progetto): deciderlo qui
alla cieca sarebbe la stessa sovrascrittura silenziosa che UX-6 vieta al parser.

## Blocco B — il PDF allegato al progetto 13

`/app/uploads/convenzioni/157055a1-c828-4de4-a60d-10ac7a3e51fb.pdf` è l'atto di
concessione che l'operatore voleva allegare. Il progetto 11 ha già la convenzione
su `convenzione_file_path`, che è un campo singolo: i due documenti non ci stanno
entrambi.

Percorso consigliato: **non spostarlo via SQL**. Dopo l'attivazione del fix,
ricaricarlo dalla scheda del progetto 11 con il nuovo flusso "allega", che passa
dal diff e lascia traccia. Fino ad allora il file resta sul disco. Nessuna query
in questo blocco.

## Blocco C — eliminazione dei doppioni

Da eseguire **solo** dopo il blocco A (altrimenti il CUP si perde) e dopo che il
PDF del 13 è stato riallegato al progetto giusto.

```sql
BEGIN;

DELETE FROM azienda_cliente_projects WHERE project_id IN (12, 13);
DELETE FROM projects WHERE id IN (12, 13);

SELECT count(*) AS progetti_rimasti FROM projects;  -- atteso: 5
ROLLBACK;  -- -> COMMIT per applicare
```

## Alternativa al blocco C — archiviare invece di cancellare

Se preferisci non perdere la traccia dei due progetti (audit, o dubbio che il 12
fosse voluto). `cancelled` è uno dei quattro stati che la UI sa mostrare
(`active | paused | completed | cancelled`): `archived` non esiste.

```sql
BEGIN;

UPDATE projects
SET status = 'cancelled',
    description = COALESCE(description || ' — ', '') ||
                  'Doppione di 11 (UX-6, bonifica 2026-07-27)'
WHERE id IN (12, 13);

SELECT id, name, status, description FROM projects WHERE id IN (11, 12, 13);
ROLLBACK;  -- -> COMMIT per applicare
```
