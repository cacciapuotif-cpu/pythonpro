# UX-5 — GATE dominio date di progetto

**Stato:** proposta, nessun codice o migration scritti  
**Data:** 2026-07-28  
**Decisione utente richiesta prima dell'implementazione**

## Problema verificato

`Project` espone oggi due campi ambigui:

- `start_date`;
- `end_date`.

La UI li chiama semplicemente “Data Inizio” e “Data Fine”. Sono opzionali alla
creazione, ma W1.5 li tratta come obbligatori quando si registra una presenza:
`crud._validate_attendance_project` blocca create/update se mancano o se la
presenza è fuori intervallo.

Quindi il vincolo W1.5 usa oggi le date ambigue del progetto. Se esse
rappresentano l'avvio/termine amministrativo del piano, la validazione delle
presenze usa il riferimento sbagliato.

Anche il Cockpit usa `Project.end_date` con due significati sovrapposti:

- progetto “oltre termine”;
- invito a verificare la rendicontazione.

Non distingue termine di attuazione, fine dell'aula e termine di
rendicontazione.

## Fonti avvisi: limite verificato

Sul DB reale:

- `avviso_regole`: **0 righe**;
- `avviso_scadenze`: **0 righe**;
- quindi regole/scadenze validate di attuazione o rendicontazione: **0**.

L'archivio contiene 7 avvisi, ma sei revisioni sono ancora nello stato
`caricato`. Solo FAPI 3/2026 ha una revisione `completata`; il markdown pulito
si ferma all'inizio dell'articolo 5 e non contiene le sezioni operative 13.7/
13.8. Sono presenti soltanto due proposte agentiche pendenti:

- una regola di attuazione sui requisiti minimi di erogazione;
- una scadenza di presentazione.

Nessuna delle due stabilisce date di avvio, conclusione o rendicontazione.
Non esiste quindi una fonte validata con cui affermare oggi i termini specifici
di FAPI, Fondimpresa e Formazienda. Tali termini non devono essere hardcoded né
dedotti da conoscenza generale: entreranno nel sistema solo dopo validazione
umana delle regole dell'avviso/revisione pertinente.

## Modello proposto

Tutte le colonne sono `DATE`, non `TIMESTAMP`: sono date amministrative o
giorni di calendario, non istanti orari.

| Campo | Significato | Obbligatorietà proposta |
|---|---|---|
| `data_approvazione` | data dell'atto/determina che approva il piano | obbligatoria per nuovi progetti attivi |
| `data_avvio_piano` | data vincolante di avvio del piano indicata nell'atto | obbligatoria per nuovi progetti attivi |
| `data_termine_piano` | termine massimo di attuazione del piano | obbligatoria quando definita dall'atto/regola; necessaria prima dell'operatività |
| `data_avvio_attivita_formative` | primo giorno effettivo di aula/formazione | nullable, valorizzata dopo |
| `data_fine_attivita_formative` | ultimo giorno effettivo di aula/formazione | nullable |
| `data_termine_rendicontazione` | scadenza entro cui rendicontare | nullable finché non nota/derivata da regola validata |
| `data_chiusura_effettiva` | giorno in cui il progetto è stato realmente chiuso | nullable |

La proposta separa `data_termine_rendicontazione` e
`data_chiusura_effettiva`. Fonderle in un unico `data_chiusura` ricreerebbe la
stessa ambiguità: una è una deadline normativa, l'altra è un fatto operativo.

## Vincoli di coerenza

Da applicare nel servizio di dominio e, per le relazioni puramente temporali,
anche con `CHECK` Alembic:

1. `data_approvazione <= data_avvio_piano`;
2. `data_avvio_piano <= data_termine_piano`;
3. se entrambe presenti:
   `data_avvio_attivita_formative <= data_fine_attivita_formative`;
4. le attività formative devono stare dentro la finestra del piano;
5. `data_termine_rendicontazione >= data_fine_attivita_formative`, quando
   entrambe presenti;
6. `data_chiusura_effettiva >= data_fine_attivita_formative`, quando entrambe
   presenti.

Non viene proposta una durata predefinita per fondo. Date assolute o offset
relativi devono provenire da atto o regola/scadenza validata.

## Backfill: esito del censimento reale

I sette record progetto dimostrano che `start_date/end_date` non hanno una
semantica uniforme:

- progetto 1: 2025-10-01 → 2026-04-30; contiene presenze e assegnazioni, ma le
  presenze sono dei collaboratori, non il registro aula degli allievi;
- progetto 5: intervallo coincidente con una singola assegnazione;
- progetto 11: intervallo coincidente con cinque assegnazioni;
- progetti 2 e 6: nessuna presenza o assegnazione che aiuti a interpretarli;
- progetto 12 archiviato: intervallo molto più ampio e discordante dal progetto
  canonico 11;
- progetto 13 archiviato: date assenti;
- `data_approvazione` è nulla su tutti i progetti.

Presenze e assegnazioni non provano l'avvio effettivo dell'aula: riguardano i
collaboratori e possono includere attività preparatorie o amministrative.

**Proposta di backfill: nessuna copia automatica** di `start_date/end_date` in
campi nuovi. I valori legacy restano conservati e visibili come “date legacy
da qualificare” finché un operatore non verifica l'atto e indica la semantica
corretta progetto per progetto.

## Migration proposta, in due fasi

### Fase 1 — additiva e reversibile

- aggiungere le sette colonne nuove, inizialmente nullable nel DB;
- aggiungere indici sulle tre scadenze usate da Agenda/Cockpit;
- aggiungere i `CHECK` che tollerano `NULL`;
- non rinominare, sovrascrivere o eliminare `start_date/end_date`;
- API/UI richiedono `data_approvazione` e `data_avvio_piano` sui **nuovi**
  progetti attivi;
- sui record legacy mostrare un badge “Date da qualificare” e un flusso di
  revisione manuale;
- auditare chi imposta o modifica ogni data.

Migration Alembic da provare su clone con upgrade/downgrade/re-upgrade e
confronto conteggi/hash prima del DB reale.

### Fase 2 — dopo la qualificazione

- spostare tutti i consumer sui campi espliciti;
- verificare che nessun progetto attivo resti senza date amministrative;
- solo allora rendere non-null i campi obbligatori e rimuovere/deprecare
  definitivamente `start_date/end_date`.

Questa sequenza soddisfa l'obbligatorietà finale senza inventare valori durante
la migration.

## Correzione W1.5 proposta

La validazione delle presenze deve usare esclusivamente:

- `data_avvio_attivita_formative`;
- `data_fine_attivita_formative`.

Comportamento:

- entrambe valorizzate → blocco se la presenza è fuori intervallo;
- una o entrambe assenti → presenza consentita con warning:
  “Registrazione su progetto senza periodo delle attività formative
  completamente dichiarato”;
- progetto `paused/completed/cancelled` → resta il blocco attuale;
- il range dell'assegnazione resta un secondo vincolo indipendente.

Il warning deve essere prodotto da un validatore di dominio condiviso tra
create e update e restituito dall'API in forma strutturata, così la UI può
mostrarlo; non basta scriverlo nei log.

Test necessari:

1. presenza dentro/fuori date attività;
2. date attività assenti → salvataggio riuscito + warning visibile;
3. date piano presenti ma attività assenti → nessun blocco basato sul piano;
4. update presenza con gli stessi casi;
5. range assegnazione ancora bloccante;
6. progetto non attivo ancora bloccante.

## UI proposta

Sezione “Date amministrative del piano”:

- Data approvazione — “Riporta la data dell'atto di approvazione”;
- Data avvio piano — obbligatoria, “Da atto di approvazione”;
- Termine attuazione del piano;
- Termine rendicontazione.

Sezione separata “Attività formative”:

- Data avvio effettivo delle attività formative;
- Data fine effettiva delle attività formative;
- testo: “Non coincide necessariamente con l'avvio amministrativo del piano”.

Sezione “Chiusura”:

- Data chiusura effettiva.

Le date attività restano modificabili dalla scheda progetto dopo la creazione.
La CONSULTAZIONE legge soltanto; ADMIN e OPERATORE seguono la matrice di
scrittura già esistente.

## Agenda e agenti

Mappatura proposta:

- `data_avvio_piano` → scadenza/adempimento “Avvio piano”;
- `data_termine_piano` → “Termine attuazione”;
- `data_fine_attivita_formative` → fatto operativo, non scadenza di
  rendicontazione;
- `data_termine_rendicontazione` → scadenza “Rendicontazione”;
- `data_chiusura_effettiva` → chiusura avvenuta.

`activity_planner` deve continuare a leggere solo `AvvisoScadenza` validate.
Una regola relativa validata può **proporre** una data di progetto ancorata
all'approvazione/avvio/fine attività; non può applicarla automaticamente.
Cockpit e Agenda leggono poi le date confermate sul progetto e mostrano la
fonte, senza usare più il generico `end_date`.

## Decisioni richieste

1. Confermare le sette date, inclusa la separazione fra termine
   rendicontazione e chiusura effettiva.
2. Confermare **nessun backfill automatico** dei campi legacy.
3. Confermare la migration additiva in due fasi: nullable nel DB per i legacy,
   obbligatorie via API/UI per i nuovi progetti.
4. Confermare il comportamento presenze: date attività mancanti = warning
   strutturato, non blocco.

Fino a conferma: **nessun codice e nessuna migration UX-5**.
