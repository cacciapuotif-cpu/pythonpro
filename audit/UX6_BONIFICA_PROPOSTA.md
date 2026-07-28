# UX-6 — Bonifica proposta (NON eseguita)

Redatta il 2026-07-27 sul DB reale `gestionale`, con analisi in **sola lettura**.
Backup di riferimento: `/DATA/progetti/pythonpro_backup_pre_ux_20260727.sql`
(1.2 MB, 58 blocchi `COPY`, marker di fine presente, `alembic_version = 063`).

> Nella redazione iniziale del 27 luglio non fu eseguito nulla. Il successivo
> blocco A è stato applicato in una sessione già chiusa; le query ancora
> proposte terminano con `ROLLBACK` e richiedono conferma esplicita.

## Aggiornamento GATE — 2026-07-28

Questa sezione fotografa lo stato corrente e prevale sui conteggi storici
sottostanti. Il blocco A proposto il 27 luglio è stato nel frattempo eseguito:
CUP e quattro associazioni allievo sono già stati travasati dal progetto 12 al
progetto 11. I blocchi B e C **non** sono stati eseguiti.

Backup fresco prima del nuovo censimento:
`/app/backups/gestionale_backup_ux6_gate_precheck_20260728_140945.sql.zip.gpg`
(cifrato; metadata/checksum presenti; decifratura e integrità ZIP:
`integrity=True`; 110367 byte).

### Censimento piani finanziari

| Controllo | Esito live |
|---|---:|
| Piani finanziari totali | 4 |
| Progetti con più di un piano | **0** |
| Piani senza progetto | **0** |
| Piani senza avviso | **0** |
| Piani senza voci | **0** |
| Duplicati per `(progetto, anno, avviso)` | **0** |
| Codici piano finanziario ripetuti | **0** |

Il sintomo chiamato operativamente “piano duplicato” non ha quindi creato un
`PianoFinanziario`: ha creato un record `Project` gemello. Nel modello corrente
l'atto/convenzione è collegato a `Project.convenzione_file_path`, non alla
tabella `piani_finanziari`.

I quattro piani sono sui progetti 1, 2, 5 e 11 e hanno rispettivamente 29, 27,
27 e 25 voci. Il solo duplicato di nome tra progetti resta:
`MAXI COMMUNICATION` → ID 11 e 12.

### Stato corrente dei tre progetti

| ID | Visibile di default | Dati propri/collegamenti correnti |
|---:|:---:|---|
| 11 | no (`is_active=false`) | progetto canonico; CUP; codice FAPI; PDF; 5 aziende; 4 allievi; 5 assegnazioni; 1 piano; 25 moduli |
| 12 | **sì** | doppione manuale; CUP e 4 allievi ora duplicati esatti del 11; 5 aziende; date discordanti; nessun'altra FK |
| 13 | no (`is_active=false`) | fantasma del bug; solo secondo PDF e 5 aziende; nessun'altra FK |

Le quattro righe `allievo_project` di 11 e 12 sono identiche campo per campo:
stessi allievi, `ore_frequentate=0`, `stato=iscritto`,
`attestato_emesso=false`, note vuote. Il travaso A è quindi verificato.

Sono state censite tutte le 14 FK verso `projects`. Su 12 e 13 esistono solo:

- progetto 12: 5 `azienda_cliente_projects` + 4 `allievo_project`;
- progetto 13: 5 `azienda_cliente_projects`;
- zero righe su ordini, piani finanziari, moduli, assegnazioni, presenze,
  dati retributivi, attività operative, esiti avviso, template, mansioni e
  collegamenti collaboratore.

### Verifica del fix

- backend mirato: `15 passed`;
- frontend mirato: `6 passed`;
- OpenAPI live: presenti i quattro endpoint project-scoped FAPI/Fondimpresa;
- bundle live `main.1f332f0e.js`: contiene le chiamate project-scoped;
- il percorso project-scoped non istanzia né `Project` né `PianoFinanziario`;
- valori vuoti vengono arricchiti, conflitti lasciati invariati salvo selezione
  esplicita campo per campo;
- il percorso senza progetto resta una creazione esplicita e rifiuta con 422
  documenti privi sia di codice sia di titolo.

### Decisione richiesta al GATE

Prima di qualunque bonifica restano due decisioni di prodotto/dominio:

1. il PDF del progetto 13 va conservato come documento del progetto 11?
   Il campo allegato è singolo e sul progetto 11 esiste già
   `/app/uploads/convenzioni/20250611CMIA001.pdf`. Il confronto read-only
   indica che il file del 13 è il candidato più completo:
   11 pagine/335642 byte contro 7 pagine/40344 byte; i testi normalizzati
   differiscono ma il documento lungo contiene integralmente quello corto
   (`similarity=0.9682`) e aggiunge l'Allegato C con CUP/COR. Il parser non lo
   riconosce perché le prime tre pagine non hanno testo estraibile, non perché
   sia estraneo. Raccomandazione: riallegare il documento lungo dalla UI,
   scegliendo esplicitamente il conflitto “Documento allegato”;
2. i progetti 12 e 13 vanno **archiviati/disattivati** (scelta reversibile,
   consigliata finché UX-5 non chiarisce le date) oppure eliminati
   definitivamente dopo il riallegamento?

In entrambi i casi va riattivato il progetto canonico 11: oggi l'elenco mostra
il doppione 12 e nasconde quello con codice FAPI, piano, moduli e assegnazioni.

### Query proposta — opzione reversibile (consigliata)

Da eseguire solo dopo la decisione sul PDF:

```sql
BEGIN;

UPDATE projects
SET is_active = TRUE,
    status = 'active'
WHERE id = 11;

UPDATE projects
SET is_active = FALSE,
    status = 'cancelled',
    description = CONCAT_WS(
        ' — ',
        NULLIF(description, ''),
        'Doppione del progetto 11; archiviato dopo verifica UX-6'
    )
WHERE id IN (12, 13);

SELECT id, name, is_active, status, description
FROM projects
WHERE id IN (11, 12, 13)
ORDER BY id;

ROLLBACK;  -- -> COMMIT solo dopo conferma
```

Questa opzione conserva le date discordanti del 12 e la traccia del 13. Non
rimuove i link duplicati, che restano storicamente associati ai record
archiviati.

### Query proposta — eliminazione definitiva

Da eseguire solo dopo il riallegamento/confronto del PDF e dopo avere
riconfermato che le sole FK su 12/13 siano quelle elencate sopra:

```sql
BEGIN;

UPDATE projects
SET is_active = TRUE,
    status = 'active'
WHERE id = 11;

-- Esplicite per rendere visibile cosa viene rimosso; le FK sono CASCADE.
DELETE FROM allievo_project
WHERE project_id = 12;

DELETE FROM azienda_cliente_projects
WHERE project_id IN (12, 13);

DELETE FROM projects
WHERE id IN (12, 13);

SELECT id, name, is_active, status
FROM projects
WHERE id IN (11, 12, 13)
ORDER BY id;

ROLLBACK;  -- -> COMMIT solo dopo conferma
```

L'eliminazione SQL non cancella automaticamente il file fisico del progetto
13: l'eventuale rimozione del PDF orfano è un'azione separata da autorizzare
solo dopo averne verificato la conservazione sul progetto 11.

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
