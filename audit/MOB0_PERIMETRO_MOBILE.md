# MOB-0 — Perimetro e strategia mobile

**Data:** 2026-07-30  
**Stato:** PROPOSTA — GATE MOB-0 IN ATTESA DI CONFERMA  
**Codice applicativo modificato:** nessuno

## Prerequisiti verificati

- Letti `STATUS.md`, `.superpowers/sdd/progress.md`,
  `audit/UI_VERIFICA_REPORT.md` (fino al GATE UI v3) e
  `audit/FINDINGS_NUOVI.md`.
- Branch `claude/platform-audit-compliance-XnH86`, locale, nessun push,
  worktree iniziale pulita.
- Ultimi 15 commit censiti.
- Backup fresco:
  `gestionale_backup_daily_20260730_020036.sql.zip.gpg`.
  Verifica reale tramite `BackupManager.verify_backup_integrity`: checksum
  coerente, decrittazione riuscita e ZIP integro (`True`).
- Ondata UX OPERATIVA: UX-5/6/7/8/9 e UX-2 risultano implementate o chiuse;
  UX-0/1/3/4 restano senza una specifica recuperabile. MOB-0 è solo
  censimento e non crea conflitti; MOB-1 non deve partire finché l'utente non
  definisce quegli scope o dichiara esplicitamente di rinviarli/annullarli.

## Principi di classificazione

1. Si classifica il **flusso**, non il contenitore: la lettura di una scheda
   può essere Livello 1 mentre il suo wizard resta Livello 3.
2. Il livello mobile non cambia il RBAC. La consultazione resta read-only;
   scritture operative restano admin/operatore; funzioni admin restano admin.
3. Livello 1 significa attività urgente, breve, contestuale, eseguibile con
   una mano e pochi tocchi.
4. Livello 2 significa consultazione utile o modifica occasionale, con una
   densità maggiore e compromessi dichiarati.
5. Livello 3 significa attività lunga, massiva, documentale, configurativa o
   ad alto rischio. Su telefono deve comparire una lettura sicura, se utile,
   oppure un messaggio desktop esplicito; mai una schermata rotta.
6. Un'azione distruttiva non diventa mobile-critical solo perché oggi compare
   nella stessa riga di un'azione frequente.

## Censimento corrente

La UI monta 21 sezioni applicative:

- admin: 21 accessibili, 20 visibili nel menu;
- operatore: 19 accessibili, 18 visibili nel menu;
- consultazione: 18 accessibili, 17 visibili nel menu.

`agents-review` è una route contestuale volutamente nascosta dal menu. I flussi
globali/pubblici aggiuntivi sono login/recupero, reset password, portale
allievi, area personale e notifiche/error boundary.

### Livello 1 — MOBILE-CRITICAL

| Pagina o flusso | Esperienza mobile richiesta | RBAC invariato |
|---|---|---|
| Login, logout, recupero e reset password | Flusso completo, tastiera corretta, errori leggibili | Pubblico/token o utente autenticato |
| Home/Cockpit | Urgenze, scadenze, contatori, apertura oggetto, azione breve con feedback | Lettura A/O/C; mutazioni solo se già autorizzate |
| Calendario | Giorno/settimana, cambio periodo, progetto, multi-collaboratore, “solo mie”, apertura evento | Lettura A/O/C |
| Presenze | Crea, consulta e modifica una presenza; elimina solo dal dettaglio con conferma forte, mai con swipe | Scrittura A/O; C sola lettura |
| Documenti mancanti e scadenze | Card per urgenza/stato, apertura documento/soggetto e sollecito singolo | Lettura A/O/C; sollecito A/O |
| Collaboratori | Ricerca, card e scheda read-only: identità, contatti, stato documenti, progetti attivi | Lettura A/O/C |
| Allievi | Ricerca, roster e scheda read-only: dati essenziali, azienda/sede, progetti/corsi | Lettura A/O/C |
| Progetti | Ricerca, card e scheda read-only: fondo/avviso, stato, date, scadenze, sede, ente, persone e moduli | Lettura A/O/C |
| Aziende clienti | Ricerca e scheda read-only: ragione sociale, sede, referente, contatti e progetti | Lettura A/O/C |
| Enti attuatori | Scheda read-only essenziale con sedi e dati legali; conti sempre mascherati | Lettura A/O/C |
| Proposte agenti | Pending, dettaglio comprensibile, approva/rifiuta/applica singola proposta dopo diff, effetto e conferma; niente azione rapida dalla card | Lettura A/O/C; decisione/apply A/O |
| Chiedi/Cerca archivio | Domanda, ricerca, risposta, fonti e apertura citazione/avviso | A/O/C |
| Area personale | Visualizza profilo e cambia password | A/O/C |
| Portale allievi | Profilo, corsi/frequenza e download attestato da magic link | Pubblico con token |
| Notifiche operative | Badge, storico persistente o aggregazione nel Cockpit, deep-link all'oggetto | A/O/C secondo oggetto |

Nota: un vero centro notifiche persistente non esiste oggi. I toast globali non
sono sufficienti; è un requisito Livello 1, non una funzione da dichiarare già
completa.

### Livello 2 — MOBILE-USABILE

| Pagina o flusso | Esperienza mobile richiesta | Eccezioni Livello 3 |
|---|---|---|
| Dashboard | KPI, compliance, contratti e volumi in card; grafici semplificati | Configurazioni/metriche tecniche |
| Timesheet | Filtri, totali, dettaglio e PDF già generati | Rigenera, sblocca, export massivo |
| Documenti | Checklist, download esplicito e upload/validazione singola | Parsing/import e operazioni massive |
| Collaboratori | Modifica contatti essenziali, upload singolo, associazione semplice | Import, contratto, operazioni massive |
| Allievi | Crea/modifica singola e collega a un progetto | Import massivo |
| Progetti | Modifica breve di stato/date/note e assegnazione singola | Wizard completo e flussi documentali |
| Aziende | Modifica breve di contatti/referente/stato | Form completo e import |
| Catalogo | Ricerca, dettaglio e modifica semplice | Disattivazioni/eliminazioni strutturali |
| Listini | Consultazione prezzi | Manutenzione listini e voci |
| Preventivi | Lista, dettaglio, PDF e transizioni di stato con conferma | Composizione/modifica righe economiche |
| Ordini | Lista, dettaglio e aggiornamento stato | Eliminazione |
| Archivio Risorse | Consultazione avvisi, revisioni e stato estrazione | Upload, ingest, parsing, disattivazione/hard-delete |
| Agents Dashboard | Stato agenti e ultimi run in lettura | Avvio manuale e controlli tecnici |
| Agenti/comunicazioni | Lettura comunicazioni e allegati autorizzati, follow-up singolo | Trigger tecnici, bulk e azioni ad alto impatto |
| Revisione avanzata | Confronto dettagli di proposte | Bulk approve/reject/apply |
| Enti attuatori | Sedi e conti mascherati | Reveal IBAN, sedi/conti e configurazione documentale |
| Area personale | Modifica dati e avatar | — |

### Livello 3 — DESKTOP-ONLY dichiarato

| Flusso | Comportamento su mobile |
|---|---|
| Creazione/modifica completa progetto, moduli, beneficiari, assegnazioni | Riepilogo read-only e messaggio desktop |
| Piano finanziario, massimali, wizard da template ed export | Riepilogo read-only e messaggio desktop |
| Upload convenzione/atto, parsing FAPI/Fondimpresa e piano XLSX | Stato/risultato read-only e messaggio desktop |
| Dissociazione forzata, cancellazioni e disattivazioni strutturali | Azione non mostrata; spiegazione desktop |
| Import massivi collaboratori/allievi/aziende | Messaggio desktop |
| Generazione contratto e template DOCX | Stato/read-only e messaggio desktop |
| Rigenera/sblocca timesheet ed export massivo | PDF read-only e messaggio desktop |
| Composizione righe preventivo e manutenzione listini | Dettaglio read-only e messaggio desktop |
| Creazione avviso, upload revisione, ingest/parsing e hard-delete | Archivio read-only e messaggio desktop |
| Enti: form completo, sedi, conti, reveal IBAN, logo/carta intestata/stampa | Scheda mascherata e messaggio desktop |
| Gestione utenti e ruoli | Eventuale elenco read-only; configurazione desktop |
| Avvio agenti, IMAP/test, trigger poll, bulk review/apply | Stato/preview read-only e messaggio desktop |

Messaggio standard proposto:

> Questa funzione è ottimizzata per computer. Apri PythonPro da desktop per
> lavorare in modo completo e sicuro.

## Casi d'uso reali

### Docente o tutor in aula

Calendario → filtra il progetto → consulta la giornata → registra/corregge una
presenza → cerca allievo, collaboratore o progetto → verifica sede e contatti.
Sono interazioni brevi, spesso con una mano occupata e rete non ideale.

### Responsabile in trasferta

Apre il Cockpit, vede scadenze e documenti, invia un sollecito singolo,
consulta azienda/progetto, valuta una proposta agente e cerca una regola con
citazione. Servono deep-link affidabili, back coerente e azioni spiegate.

### Titolare che controlla la sera

Controlla urgenze, KPI sintetici, preventivi/ordini e decisioni agentiche.
Può approvare una singola azione chiaramente spiegata; non deve compilare piani
finanziari, configurare enti o manipolare file complessi dal telefono.

## Navigazione mobile proposta per MOB-2

La bottom navigation deve essere role-aware senza ampliare i permessi:

| Profilo | Destinazioni |
|---|---|
| Admin/Operatore | Home · Calendario · Presenze · Proposte · Altro |
| Consultazione | Home · Calendario · Persone · Archivio · Altro |

`Altro` apre il menu completo full-screen, ricercabile e raggruppato secondo la
struttura applicativa reale. L'header mobile mostra titolo, azione contestuale
sicura, notifiche e profilo. Le aree inferiori rispettano la safe area iOS.

## Esclusioni

`AgenzieManager`, `ConsulentiManager`, `ProgettoMansioneEnteManager` e
`CalendarSimple` sono componenti orfani/non montati. Non sono pagine operative
e restano fuori dall'Ondata Mobile salvo decisione di prodotto separata.

## Blocchi prima di MOB-1

1. Conferma esplicita del presente GATE MOB-0.
2. Decisione sugli scope mancanti UX-0/1/3/4: fornirli e completarli, oppure
   dichiararli rinviati/annullati. Nessun lavoro responsive sugli stessi
   componenti deve iniziare nel frattempo.
3. Ripristinare una baseline di suite completa realmente verde: l'ultima
   esecuzione locale ha 7 failure e 241 errori di startup/fixture, già
   confermati preesistenti su HEAD pulito. La non-regressione mobile non può
   poggiare su una baseline rossa.

## Decisioni richieste al GATE

1. Confermare i tre livelli e la separazione lettura/modifica.
2. Confermare **Allievi read-only** nel Livello 1.
3. Confermare che “Proposte” Livello 1 significhi singola decisione spiegata e
   auditata, non la piattaforma tecnica Agenti.
4. Confermare le bottom navigation differenziate per ruolo.
5. Confermare che notifiche persistenti/scadenze siano un requisito Livello 1.
6. Definire o rinviare esplicitamente UX-0/1/3/4 prima di MOB-1.

