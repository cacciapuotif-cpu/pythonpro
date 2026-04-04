# Audit Tecnico ERP Formazione Finanziata
_Data: 2026-04-04_

## Obiettivo
Tradurre l'analisi architetturale del repository in un quadro operativo: moduli maturi, moduli parziali, gap verso un ERP completo e prerequisiti per agenti autonomi.

## Sintesi Esecutiva
PythonPro ha gia una base dati e applicativa coerente con un ERP verticale per formazione finanziata. Il repository non e piu una semplice CRUD app: contiene dominio operativo, budget/piani, presenze, assegnazioni, template documentali, reporting, modulo commerciale e una prima infrastruttura per agenti AI.

Il limite attuale non e principalmente di schema o di anagrafiche. Il limite e di orchestrazione:
- i moduli esistono ma non sempre chiudono un workflow end-to-end
- molte regole sono applicative e non presidiate da vincoli DB forti
- la rendicontazione automatica e la gestione documentale risultano ancora parziali
- gli agenti AI sono gia predisposti, ma non ancora inseriti in una macchina operativa completa con SLA, retry, policy e canali esterni robusti

## Mappa Moduli

### Moduli sostanzialmente maturi
| Modulo | Stato | Evidenze |
|---|---|---|
| Collaboratori | Avanzato | Anagrafiche estese, documenti, upload, flag agenzia/consulente, CRUD e validazioni applicative |
| Progetti | Avanzato | Collegamenti con ente attuatore, template piano, fondo/avviso, relazioni con presenze e piani |
| Enti attuatori | Avanzato | Modello dedicato, relazioni con progetti e associazioni progetto-mansione-ente |
| Assegnazioni | Avanzato | Periodi, ore, costo, contratto, controlli overlap/date in service layer |
| Presenze / Timesheet | Avanzato | Validazione intervalli, conflitti orari, collegamento ad assegnazioni, reporting |
| Template documentali / contratti | Avanzato | Contestualizzazione per ambito, progetto, ente erogatore, avviso, chiave documento |
| Piano Finanziario Formazienda | Avanzato | Piano, voci, riepilogo, export Excel, confronto pianificato/effettivo |
| Piano Fondimpresa | Strutturalmente ricco | Tabelle dedicate per voci, budget, documenti, nominativi |
| Commerciale (aziende, preventivi, ordini, listini) | Buona base | Dominio gia presente e relazioni lato CRM/commerciale |
| AI Agent Core | Avanzato come base tecnica | Registry agenti, run, suggestion, review, draft communication, workflow operatore |

### Moduli parziali o ancora orientati a CRUD + supporto operativo
| Modulo | Stato | Gap principale |
|---|---|---|
| Rendicontazione end-to-end | Parziale | Manca un motore completo che chiuda il ciclo presenze -> costi -> giustificativi -> avanzamento finanziario |
| Gestione documentale avanzata | Parziale | Upload e template presenti, ma non emerge una filiera completa con versioning, protocollazione, firma, checklist e scadenze |
| Workflow approvativi | Parziale | Ci sono alert/task e review agenti, ma non un motore trasversale per stati, eccezioni, escalation e audit completo di processo |
| Calendarizzazione operativa complessa | Parziale | I controlli di conflitto ci sono, ma non emerge un vero motore di pianificazione risorse/calendari multi-attore |
| Comunicazioni omnicanale | Parziale | Email abbozzata/attivabile, WhatsApp non ancora integrato come provider reale |
| Test business-critical | Debole | I test visibili sono smoke/API base, non una rete ampia di regressione su regole complesse |

### Moduli mancanti o non ancora evidenti
| Modulo | Stato | Nota |
|---|---|---|
| Workflow engine durabile | Assente o non esplicito | Mancano segnali di orchestratore persistente stile saga/BPM |
| Policy engine centrale | Assente | Le decisioni sono sparse tra router, CRUD e validator |
| Document intelligence | Assente | Nessuna evidenza di OCR/classificazione/estrazione strutturata documenti |
| Integrazione forte con PEC/firma/protocollo | Non evidente | Non rilevata nel perimetro ispezionato |
| Metriche agenti / observability AI | Parziale | Base persistente presente, ma non una telemetria completa su successo, retry, latenza, qualità |

## Backlog Tecnico Prioritizzato

### Priorita 1: chiudere i workflow core
1. Rendicontazione guidata da regole
   - derivare automaticamente costi e avanzamenti da assegnazioni, presenze e voci piano
   - gestire scostamenti, saturazioni budget, mismatch documentali
2. Workflow documentale per collaboratori e progetto
   - checklist documenti obbligatori per ruolo, fondo, avviso, ente
   - stati: richiesto, inviato, verificato, scaduto, respinto
3. Workflow operatore unificato
   - inbox unificata task/alert/agent suggestions
   - azioni standard: approva, attendi, richiedi integrazione, chiudi, sollecita

### Priorita 2: consolidare le regole critiche
1. Rafforzare i vincoli applicativi con protezioni piu robuste
   - hardening concorrenza sui controlli overlap
   - verificare se alcune regole vanno duplicate a DB
2. Centralizzare le regole di business
   - estrarre decisioni sparse in un rule/policy layer
3. Ampliare la copertura test
   - overlap orari
   - range assegnazioni
   - saturazione ore/costi
   - coerenza piano vs presenze vs contratti

### Priorita 3: integrazioni esterne
1. Email outbound affidabile con audit e retry
2. Provider WhatsApp reale
3. Integrazione documentale esterna
   - firma
   - PEC o canali formali
   - eventuale protocollo/conservazione

### Priorita 4: agenti autonomi
1. Event bus o trigger standardizzati
2. Scheduler/worker durabile per follow-up, reminder, escalation
3. Metriche agenti e health per workflow
4. Policy di autonomia
   - cosa puo fare un agente da solo
   - cosa richiede approvazione operatore
   - come gestire retry, timeout, failure

## Roadmap in 3 Fasi

### Fase 1: Stabilizzazione ERP operativo
Obiettivo: rendere solidi i flussi gia presenti e ridurre il delta tra CRUD e processo.

Deliverable:
- checklist dati obbligatori per collaboratore/progetto/piano
- workflow documentale minimo
- inbox operatore unificata
- test sulle regole critiche di presenze e assegnazioni
- audit log piu leggibile per eventi chiave

Esito atteso:
- il sistema smette di essere una raccolta di moduli e diventa una piattaforma operativa coerente

### Fase 2: Automazione business
Obiettivo: trasformare i dati gia raccolti in processi automatici.

Deliverable:
- rendicontazione assistita con scostamenti e alert
- follow-up automatici su documenti mancanti/scaduti
- azioni schedulate su scadenze, solleciti, saturazioni ore e budget
- motore regole centralizzato per eccezioni e blocchi operativi

Esito atteso:
- meno lavoro manuale di controllo, piu supervisione per eccezione

### Fase 3: Agenti autonomi governati
Obiettivo: introdurre agenti con autonomia controllata.

Deliverable:
- agente data quality sempre attivo su eventi di dominio
- agente outreach/document recovery multicanale
- agente assistente rendicontazione con proposte di correzione e riconciliazione
- telemetria agenti, policy di approvazione, retry/escalation

Esito atteso:
- gli agenti non sono solo "bottoni" ma operatori software incastonati nei workflow

## Gap Specifici per Agenti Autonomi
Per supportare agenti realmente autonomi servono ancora questi blocchi:

1. Eventi di dominio standard
   - creazione/modifica collaboratore
   - caricamento documento
   - scadenza documento
   - nuova presenza
   - saturazione voce di piano

2. Stato di workflow esplicito
   - non basta salvare suggestion e draft
   - serve una macchina a stati coerente per task, reminder, esiti e chiusure

3. Connettori outbound affidabili
   - email e WhatsApp con delivery tracking, retry, failure handling

4. Policy e guardrail
   - distinguere azioni suggeribili da azioni eseguibili autonomamente
   - mantenere audit completo di decisione, contenuto inviato e outcome

5. Misurazione
   - numero task aperti/chiusi
   - tempo medio di risoluzione
   - successo dei solleciti
   - falsi positivi dell'agente

## Valutazione Finale
Stato complessivo: avanzato, ma non ancora ERP completo.

Giudizio sintetico:
- schema: forte
- dominio: ben impostato
- moduli core: in buona parte presenti
- workflow: ancora il vero collo di bottiglia
- AI readiness: buona base tecnica, maturita operativa ancora intermedia

Se il prossimo obiettivo e "ERP completo per formazione finanziata", la sequenza corretta non e aggiungere altri moduli isolati. La sequenza corretta e:
1. chiudere i workflow tra moduli gia esistenti
2. consolidare regole/test/integrita operativa
3. solo dopo, alzare il grado di autonomia degli agenti
