# Backlog Implementativo ERP Formazione Finanziata
_Data: 2026-04-04_

## Scopo
Convertire l'audit tecnico in un backlog eseguibile, ordinato per epic, outcome e sequenza di implementazione.

## Ordine di esecuzione raccomandato
1. Chiudere il workflow documentale collaboratore
2. Consolidare il motore regole e i test sulle regole critiche
3. Chiudere la rendicontazione assistita progetto/piano
4. Stabilizzare i canali outbound e il workflow engine
5. Estendere l'autonomia degli agenti

## Epic 1 — Workflow Documentale Collaboratore
Obiettivo: chiudere davvero il ciclo `dato mancante -> task operatore -> richiesta -> risposta/sollecito -> chiusura`.

### Stato attuale
- esistono `data_quality`, inbox operatore, review actions, draft email/whatsapp, follow-up schedulato
- manca una checklist documentale formalizzata e riusabile per fondo/avviso/ruolo/ente

### Task
1. Introdurre checklist documentale strutturata
   - modello/tabella per requisiti documentali
   - chiavi minime: `entity_type`, `ruolo`, `fondo`, `ente_erogatore`, `avviso`, `document_key`, `required`, `expiry_required`
2. Derivare il profilo documentale richiesto del collaboratore
   - servizio che calcola i documenti obbligatori in base al contesto
3. Distinguere chiaramente task di profilo vs task di documento
   - `missing_profile_fields`
   - `missing_required_document`
   - `expired_required_document`
4. Mostrare checklist nel dettaglio collaboratore
   - sezione con stato per ciascun requisito
5. Consentire chiusura automatica task quando il documento arriva
   - evento su upload/aggiornamento scadenza
6. Aggiungere esito workflow
   - `resolved_by_upload`
   - `resolved_by_operator`
   - `abandoned`

### Output atteso
- il collaboratore ha un fascicolo documentale esplicito
- il task agente non e piu generico, ma agganciato a requisiti verificabili

## Epic 2 — Motore Regole e Integrita Operativa
Obiettivo: togliere logica critica dai punti sparsi e renderla verificabile.

### Stato attuale
- i controlli esistono ma sono distribuiti tra router, CRUD, validator e modello

### Task
1. Estrarre un layer `business_rules/`
   - presenze
   - assegnazioni
   - documenti
   - piani finanziari
2. Rendere idempotenti i check critici
   - overlap presenze
   - range assegnazioni
   - ore residue
3. Valutare vincoli DB aggiuntivi
   - unique mirate
   - check constraint dove sensato
   - locking/transaction strategy sui punti concorrenti
4. Copertura test
   - test unit su rule layer
   - test integrazione sui casi di conflitto
   - test regressione su aggiornamenti presenza/assegnazione

### Output atteso
- regole centrali e testabili
- minore rischio di regressioni silenziose

## Epic 3 — Rendicontazione Assistita
Obiettivo: chiudere il collegamento tra assegnazioni, presenze, costi e piani.

### Stato attuale
- esistono piano, voci, riepiloghi, aggregazioni ore, export
- manca il workflow che governa gli scostamenti e le eccezioni

### Task
1. Motore scostamenti piano
   - preventivo vs consuntivo
   - ore previste vs effettive
   - saturazione voci
2. Alert operativi di rendicontazione
   - costo fuori soglia
   - ore eccedenti
   - presenza senza giustificativo o assegnazione corretta
3. Vista operatore rendicontazione
   - elenco anomalie per progetto/piano
4. Task agentici di correzione
   - proposta riallocazione
   - richiesta documento
   - segnalazione blocco export

### Output atteso
- il piano finanziario non e solo un contenitore dati, ma un presidio di controllo operativo

## Epic 4 — Workflow Engine e Canali Outbound
Obiettivo: rendere affidabili stati, reminder, invii e retry.

### Stato attuale
- ARQ presente
- follow-up schedulato presente
- email base presente
- WhatsApp ancora draft-only

### Task
1. Unificare gli stati workflow
   - task
   - communication
   - reminder
   - outcome
2. Delivery tracking outbound
   - `queued`, `sent`, `delivered`, `failed`, `retry_scheduled`
3. Retry policy
   - backoff
   - max attempt
   - escalation a operatore
4. Provider WhatsApp reale
5. Log tecnico e business dell'invio

### Output atteso
- le comunicazioni non sono best-effort, ma processi osservabili e governati

## Epic 5 — Agenti Autonomi Governati
Obiettivo: aumentare l'autonomia senza perdere controllo.

### Stato attuale
- base agentica presente
- manca uno strato chiaro di autonomia controllata

### Task
1. Standardizzare eventi di dominio
   - collaborator.created/updated
   - document.uploaded
   - attendance.created
   - assignment.updated
   - piano.threshold_exceeded
2. Policy di autonomia
   - azioni consentite senza approvazione
   - azioni con approvazione obbligatoria
3. Telemetria agenti
   - successo
   - tempo di chiusura
   - fallimenti
   - falso positivo
4. Agente rendicontazione
5. Agente document intelligence

### Output atteso
- agenti realmente utili e misurabili, non solo dimostrativi

## Primo Workflow da Realizzare Subito
Workflow raccomandato: `Collaboratore -> documenti mancanti -> richiesta -> sollecito -> chiusura`

### Perche questo per primo
- usa moduli gia esistenti
- genera valore operativo immediato
- stressa agenti, notifiche, stati e documenti nello stesso flusso

### Sequenza tecnica suggerita
1. Tabella requisiti documentali
2. Servizio di calcolo checklist per collaboratore
3. Nuovi suggestion type dedicati ai documenti
4. Sezione checklist nel dettaglio collaboratore
5. Chiusura automatica task su upload valido
6. Sollecito multicanale con tracking esiti
7. KPI dashboard su pratiche aperte, scadute, risolte

## Criteri di completamento
Un epic si considera chiuso solo se ha:
- modello dati stabile
- API operative
- UI minima utilizzabile
- job/scheduler se richiesto
- test su casi nominali e casi critici
- audit log sugli eventi principali

## Prossimo Step Raccomandato
Aprire subito Epic 1, partendo dal modello requisiti documentali e dalla checklist collaboratore.
