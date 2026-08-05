# PythonPro — Stato corrente

**Aggiornato:** 2026-08-05 (smoke live Formazienda + punto di accesso Formulario mancante nella UI progetto)
**Branch:** `claude/platform-audit-compliance-XnH86` (locale, **nessun push**)
**Percorso:** `/DATA/progetti/pythonpro`

## ✅ FORMAZIENDA — FORMULARIO RAGGIUNGIBILE DALLA SCHEDA PROGETTO — 2026-08-05

Durante la prova live e' emerso che `FormularioFormaziendaModal` e i relativi
endpoint esistevano, ma `ProjectManager` montava `FapiUploadSection` nelle
schede solo se il progetto era FAPI. Corretto con la funzione condivisa
`mostraDocumentiFondo`: la sezione viene ora montata per FAPI, Fondimpresa e
Formazienda, senza mostrarla sui progetti manuali generici. Percorso desktop:
Progetti -> scheda progetto Formazienda -> Documenti Formazienda -> Carica
Formulario (Allegato A).

Verifiche: `ProjectManager.associati.test.js` + `FapiUpload.test.js`, **25/25**;
build produzione verde; frontend ricostruito e ricreato; health live HTTP 200;
bundle servito `main.7bf5c35c.js` con il marker `Carica Formulario (Allegato
A)`. Da telefono l'upload resta intenzionalmente desktop-only come deciso nel
gate MOB-4.

Smoke live autorizzato sul deploy: lista progetti HTTP 200; moduli progetto
#11 HTTP 200 (25 moduli, 207 ore, 5 gruppi); creazione manuale progetto con
`data_approvazione` e `data_avvio_piano` HTTP 200; upload Allegato E HTTP 200;
confirm HTTP 200, documento versionato creato. Il record temporaneo #17, il
documento #8, due file di upload e una preview Redis residua sono stati rimossi
esattamente. Verifica finale: progetto #17 = 0, documento #8 = 0, preview #17 =
0. Il comando iniziale aveva un ritorno a capo errato prima dell'URL di confirm
e import ORM incompleti nel cleanup; la prova e la pulizia sono state completate
con comandi corretti.

## ✅ WIZARD MANUALE: DATA APPROVAZIONE/AVVIO PIANO MANCANTI — 2026-08-04

Trovato dal vivo mentre l'utente testava il lavoro Formazienda su
`192.168.2.41:8001`: "+ Nuovo Progetto" (percorso manuale, non da upload
documento) falliva sempre con 400 — bug preesistente, scorrelato.
Dettagli, causa e fix in `REMEDIATION_LOG.md` (PRJ-WIZARD-MANUALE-DATE-MANCANTI).
Non deployato sul container live. Commit locale `6ad26ef`.

## ✅ FORMAZIENDA — ATTO DI ADESIONE E FORMULARIO RICONOSCIUTI COME ATTO CONCESSORIO — 2026-08-04

**Compito:** l'utente era bloccato a meta' creazione di un progetto reale:
il wizard "Nuovo progetto" trattava il documento di concessione come se
fosse sempre la convenzione FAPI (ente + aziende beneficiarie + codici
progetto). L'Allegato E Formazienda porta l'ente ma **mai** aziende
beneficiarie: caricarlo lasciava l'ente attuatore "Non disponibile" e la
Delivery bloccata per sempre, perche' il flusso "Formazienda" nel wizard
era un `PlaceholderDocumentModal` — nessuna chiamata al backend, nessun
progetto creato davvero.

**Causa radice trovata:** tre problemi distinti, non uno solo.
1. Il modale Formazienda del wizard era letteralmente finto (nessun
   endpoint dietro).
2. Il gate "ha convenzione" controllava solo `tipo_documento == "convenzione"`,
   mai `"atto_concessione"` (il tipo che Formazienda avrebbe dovuto usare).
3. Il picker aziende della Delivery era incondizionatamente perimetro-ristretto
   alle aziende create dalla convenzione: per un fondo che non le fornisce,
   il perimetro resta vuoto per sempre e blocca la selezione manuale anche
   dopo aver sbloccato l'ente.

**Cosa e' stato costruito** (piano completo in
`docs/superpowers/plans/2026-08-04-formazienda-atto-adesione.md`, 16 task):
- `services/atto_concessorio_registry.py`: dichiarazione per fondo di cosa
  fornisce l'atto concessorio (ente si/no, aziende si/no). FAPI invariato
  (fornisce entrambi); Formazienda dichiara aziende=no; Fondimpresa
  predisposto nella struttura ma non attivato (nessun cambio al suo router
  esistente, che oggi non versiona documenti).
- Gate `crud.project_has_current_convenzione` esteso ad accettare anche
  `atto_concessione`.
- Delivery selettiva: `crud._validate_delivery_update` e
  `routers/projects.py` (`delivery-companies`, `delivery-companies/.../students`)
  usano il catalogo globale invece del perimetro quando il fondo non
  dichiara aziende. FAPI resta perimetro-ristretto (nessuna regressione).
- `services/documento_progetto.archivia_documento_progetto`: estratta da
  `convenzione_upload._archivia_documento` per essere condivisa tra router.
- `services/parsers/formazienda/atto_adesione_parser.py`: piano, avviso,
  importi A/B/C, ente attuatore e legale rappresentante dall'Allegato E
  reale, con le due trappole gestite dal contesto della frase (piede di
  pagina = approvazione del modulo, non del piano; sottoscrizione = firma
  digitale, non emissione).
- `routers/formazienda_upload.py`: upload/confirm Atto di adesione
  (crea o associa progetto) + upload/confirm Formulario (Allegato A,
  sempre dentro un progetto esistente: i due documenti sono complementari).
- `services/parsers/formazienda/formulario_parser.py`: soggetto gestore,
  soggetto delegato (con importo/percentuale), 14 imprese beneficiarie con
  tutti i dati identificativi, progetto formativo, macrovoci A/B/C/D con
  limiti dichiarati, cronoprogramma, con doppia verifica di quadratura
  (edizioni x finanziamento/edizione, macrovoci vs preventivo, somma per
  impresa vs costo complessivo) che segnala invece di importare numeri
  incoerenti.
- Migration 074: `AziendaCliente.classe_dimensionale` (il dato piu'
  prezioso dell'Allegato A) e tabella `project_soggetti_delegati` (la
  delega e' verificata dai controlli del fondo, va registrata non solo
  mostrata). Non applicata a nessun DB reale.
- Frontend: `AttoAdesioneFormaziendaModal` e `FormularioFormaziendaModal`
  sostituiscono il placeholder; hint di ricerca aziende differenziato per
  fondo nello Step Delivery.

**Confutatore** (cosa ho provato a smentire prima di chiudere):
- *"Forse il perimetro vuoto non e' un problema reale, magari l'operatore
  puo' comunque salvare senza aziende"* — no: `_validate_delivery_update`
  rifiutava con 422 qualunque `azienda_ids` non gia' nel perimetro, quindi
  un progetto Formazienda con zero aziende linkate dal parser non poteva
  MAI ricevere aziende via Delivery, nemmeno una alla volta. Verificato con
  test che riproduce esattamente questo scenario (`test_formazienda_aziende_selezionabili_dal_catalogo_globale`)
  prima del fix, dove falliva con "Aziende fuori dal perimetro".
- *"Forse i regex sulle trappole (data approvazione, sottoscrizione)
  funzionano solo sul testo descritto a voce, non sul PDF vero"* — costruiti
  e testati contro `imports/formazienda/ALLEGATO E.pdf` e `ALLEGATO A.pdf`
  reali (non fixture sintetiche): il footer "Data approvazione: 03/08/2022"
  compare 4 volte nell'Allegato E e non e' mai stato preso per la delibera
  del piano (11/06/2026, verificato dal test).
- *"Forse estendere il gate a `atto_concessione` rompe qualcosa per FAPI o
  Fondimpresa"* — suite completa backend eseguita due volte dopo il
  cambio (prima e dopo Task 14): 1065 passed, 8 skipped, zero regressioni
  nei test FAPI/UX-6/Fondimpresa esistenti.
- *"Forse i dati dell'Allegato A rompono la creazione azienda per qualche
  vincolo del modello"* — successo: `AziendaCliente.provincia` richiede
  la sigla di 2 lettere ma l'Allegato A riporta il nome esteso della
  provincia ("NAPOLI" non "NA"). Trovato SOLO eseguendo il test contro il
  PDF reale (non sarebbe emerso da dati sintetici); risolto non mappando
  quel campo invece di inventare una tabella di conversione.

**Verifica reale eseguita** (automatica, non browser — vedi nota sotto):
- Backend: `pytest` completo, **1065 passed, 8 skipped**, eseguito due volte
  (dopo Task 6 e dopo Task 15) su schema SQLite generato da `models.py`.
- Frontend: `react-scripts test --watchAll=false` completo, **338 passed**,
  **1 failed** in `PianoTemplateWizard.test.js` (interazione Escape/conferma
  su un componente mai toccato da questo lavoro — pre-esistente, non una
  regressione: verificato che l'ultimo commit su quel file precede questa
  sessione).
- Parser Allegato E: 6/6 test contro il PDF reale, incluse le due trappole
  verificate sul documento (`test_formazienda_atto_adesione_parser.py`).
- Parser Allegato A: 11/11 test contro il PDF reale (14 imprese, ditta
  individuale con CF personale diverso da P.IVA, campi vuoti, quadratura
  costo progetto, macrovoci, cronoprogramma) (`test_formazienda_formulario_parser.py`).
- Router end-to-end (upload→confirm, via `TestClient` con i PDF reali):
  6/6 in `test_formazienda_upload.py`, incluso il caso file illeggibile
  (archiviato comunque, nessun 500).
- **Non eseguita**: verifica manuale nel browser reale (docker-compose non
  avviato — rischio di toccare un DB potenzialmente condiviso con dati
  reali senza autorizzazione esplicita). Le sei prove del Punto 5 e le
  otto del punto Allegato A sono verificate via `TestClient` FastAPI
  contro i PDF reali, non via UI cliccata; equivalente funzionale, non
  equivalente visivo.

**Esiti dei sei casi (Allegato E, dal compito originale):**
1. Progetto Formazienda da `ALLEGATO E.pdf` → ente derivato (NEXT GROUP
   S.R.L.), nessun blocco residuo: **verificato**
   (`test_confirm_crea_progetto_formazienda_con_ente_derivato_e_nessun_blocco`).
2. Aziende/sedi/allievi selezionabili a mano, progetto si crea: **verificato**
   (`test_formazienda_aziende_selezionabili_dal_catalogo_globale`).
3. Data approvazione piano = 11/06/2026 (delibera, non 03/08/2022 del
   piede di pagina); sottoscrizione = 01/07/2026 (firma digitale, non
   10/08/2022 emissione); importi A/B/C = 55.440,00 / 0,00 / 55.440,00:
   **verificato** (`test_trappola_*`, `test_importi_a_b_c`).
4. Documento archiviato nel progetto (`tipo_documento="atto_concessione"`,
   versionato): **verificato**. Archivio Risorse: quella sezione oggi
   e' Avvisi-only (bandi/regolamenti), non documenti di progetto —
   nessuna falsa dichiarazione qui, i documenti di progetto restano
   nell'endpoint `/{project_id}/documenti` come per FAPI.
5. Progetto FAPI con convenzione: nessuna regressione, aziende ancora
   proposte dal documento: **verificato** (suite `test_project_delivery_scope.py`
   e `test_ux6b_bivio_convenzione.py` invariate, 47+ test verdi).
6. Documento illeggibile: archiviato comunque, inserimento manuale
   possibile: **verificato** (`test_documento_illeggibile_si_archivia_comunque_e_permette_inserimento_manuale`).

**Esiti degli otto casi (Allegato A, aggiunta al compito):**
1. 14 imprese estratte con ragione sociale reale, P.IVA, ATECO, matricola
   INPS, classe dimensionale, regime de minimis: **verificato**.
2. Soggetto Gestore (NEXT GROUP) assente dalle beneficiarie: **verificato**.
3. Soggetto Delegato (A.M.D. S.R.L.) registrato con importo 14.000,00 €
   e percentuale 25,25%: **verificato**.
4. Progetto formativo con ore (24), edizioni (14), ripartizione aula
   (14h/58,33%) + training on the job (10h/41,67%): **verificato**.
5. Macrovoci quadrano col totale (A 20% max, B, C 30% max, D), somma per
   impresa coincide col costo complessivo: **verificato**.
6. Cronoprogramma popola le 4 attivita' come proposta (mese/anno, mai un
   giorno inventato): **verificato**.
7. Allegato E + Allegato A sullo stesso progetto: nessun dato duplicato,
   divergenze segnalate nei warning: **verificato**
   (`test_divergenza_tra_allegato_a_ed_e_viene_segnalata`).
8. Entrambi i PDF archiviati sul progetto (`atto_concessione` +
   `formulario`): **verificato**.

**Commit locali** (nessun push): `c57ccec` → `9255b18`, 16 commit atomici,
uno per task del piano. Vedi `git log --oneline c57ccec^..9255b18`.

**ATTO DI ADESIONE FORMAZIENDA RICONOSCIUTO COME ATTO CONCESSORIO: SÌ**

## ✅ DELIVERY DERIVATA DA CONVENZIONE E PERIMETRO PROGETTO — 2026-08-03

Chiuso il caricamento globale dello Step 3 Delivery. La ricognizione ha
confermato che non esiste una FK `convenzione_id`: la convenzione e' un
`ProjectDocumento`, mentre `azienda_cliente_projects` e' il perimetro aziende
materializzato dalla conferma del documento. Non e' servita una migration.

- `GET /projects/{id}/delivery-context` espone la convenzione corrente e
  l'ente attuatore derivato; senza convenzione restituisce il motivo bloccante
  `Collega prima la convenzione al progetto`.
- `GET /projects/{id}/delivery-companies` richiede sempre il progetto, filtra
  esclusivamente i link di quel progetto, ricerca su ragione sociale/P.IVA con
  `q`, `limit` (20, max 50) e `offset`; il payload non contiene allievi o loro
  conteggi.
- Gli allievi arrivano solo da
  `/projects/{id}/delivery-companies/{azienda_id}/students`, dopo espansione
  esplicita dell'azienda. Il frontend non usa piu' `getAziendeClienti` ne'
  `caricaTuttiGliAllievi` nel wizard.
- L'ente e' read-only. Il PUT del wizard viene rifiutato con 422 se manca la
  convenzione o se l'ente inviato non coincide con quello del progetto.
- Nuovo typeahead con debounce e paginazione server-side; nessun filtro locale
  del catalogo e nessun preload allievi.

Test aggiunti senza modificare i test esistenti: 8 backend (incluso seed 500
aziende, 480 fuori perimetro) e 2 frontend. Suite complete dopo il follow-up:
backend **1034 passed / 8 skipped**, frontend **45 suite / 336 test**, build
produzione verde.
Confutatore: rimosso temporaneamente il filtro `project_id`; il test di
perimetro e' diventato rosso (`{1,2,3,4,5}` contro `{1,2,3,4}`), poi il filtro
e' stato ripristinato e lo stesso test e' tornato verde.

Follow-up sulla discrepanza Home/Delivery: il context ora espone sempre in sola
lettura l'ente gia' identificato sul progetto, mantenendo il blocco operativo
se manca una convenzione corrente. Inoltre `formulario` e `piano_finanziario`
non sovrascrivono piu' il vecchio `convenzione_file_path`; la UI FAPI dichiara
una convenzione caricata solo se esiste davvero un `ProjectDocumento` corrente
di tipo `convenzione`. Commit locali `bc2ed37` e `3b79724`, nessun push.

Runtime ricostruito e ricreato, backend/frontend healthy, bundle live
`main.4c6bd77a.js`. Verifica autenticata reale sul progetto #11: context HTTP
200, `ente_attuatore=Next Group srl`, `has_convenzione=true`. Alle 16:38 locali
risulta infatti aggiunto il documento corrente
`convenzioneAvviso012022_20250611CMIA001.pdf`, distinto dal formulario del
31 luglio. Nessun dato reale e' stato creato o alterato durante il follow-up.

La sede di prova creata al caso 5 del collaudo UI reale e' stata rinominata,
su autorizzazione utente, da `Aula Delivery UI 1785753389697` a
`Martinelli Carmela - Sede AZ11-008`: ragione sociale + codice stabile composto
da azienda 11 e sede 8, senza riferimenti a Delivery. API update HTTP 200 e
successiva lettura progetto #11 confermano il nuovo nome sia in anagrafica sia
nel Delivery; indirizzo e associazioni sono rimasti invariati.

**DELIVERY PERIMETRATA DALLA CONVENZIONE: SI'.**

## ✅ FIX INVIA SOLLECITO DOCUMENTI — 2026-08-03

Corretto il caso reale in Documenti Mancanti: il pulsante “Invia sollecito”
usava `window.open(mailto:...)`, quindi il browser apriva il provider email
associato al protocollo `mailto` (nel caso osservato, login Libero) invece di
inviare dall'applicazione.

Il frontend ora chiama `POST /api/v1/documenti-richiesti/sollecita`; il backend
raggruppa i documenti richiesti/scaduti per collaboratore, invia una sola email
tramite l'SMTP PythonPro e il template `sollecito_documento`, registra l'esito
in `audit_log` e restituisce un messaggio visibile. Ruoli ammessi: admin e
operatore; consultazione bloccata. Il bulk usa lo stesso percorso. L'URL di
caricamento deriva da `DOCUMENT_UPLOAD_URL_BASE` oppure, in fallback sicuro,
dall'origine di `PASSWORD_RESET_URL_BASE`. Rimossi dal template logo e contatti
segnaposto.

Verifiche: backend mirato email/sicurezza **14 passed**; frontend dedicato
**2 passed**; build produzione verde. Backend/frontend ricostruiti e ricreati;
entrambi healthy, health HTTP 200, endpoint presente in OpenAPI e bundle live
`main.f0264d75.js` contiene `documenti-richiesti/sollecita`. SMTP e URL pubblico
risultano configurati, `SMTP_TEST_MODE=false`; autenticazione SMTP reale
verificata `ok` senza inviare messaggi. Nessuna email reale inviata nei
test/smoke. Prossimo passo utente: ricaricare la pagina e riprovare “Invia
sollecito”; deve restare in PythonPro e mostrare l'esito dell'invio.

## ✅ RIPRISTINO RUNTIME — 2026-08-01

PythonPro non era raggiungibile sulla porta `3001`: frontend fermo e backend
in uscita durante il bootstrap. Causa: modifica DATE-2 incompleta in
`backend/models.py`; `Project` dichiarava una relazione verso
`ProjectTermState`, ma il modello non era definito/registrato. Rimosso soltanto
il blocco di relazione incompleto, preservando gli alias data DATE-2 e le altre
modifiche locali; nessuna migration o modifica DB eseguita.

Stack riavviato con Docker Compose. Verifica finale: backend, frontend, Redis,
PostgreSQL e ARQ worker healthy; `http://127.0.0.1:3001` risponde `200 OK`;
health frontend/proxy e backend entrambi `{"status":"ok"}`. Nessun commit e
nessun push.

Secondo ripristino nella stessa giornata: interfaccia raggiungibile ma liste
progetti, collaboratori e avvisi vuote. I dati erano integri nel DB reale
(2 progetti, 23 collaboratori, 2 avvisi); le API fallivano perché il modello
DATE-2 conteneva anche `Project.data_sottoscrizione`, colonna non ancora
presente nello schema Alembic 070. Rimosso esclusivamente il campo incompleto
dal modello, senza migration e senza modifiche ai dati, quindi riavviato il
backend. Verifica ORM post-fix: progetti #5 `poppi` e #11
`MAXI COMMUNICATION`, 23 collaboratori con relazioni leggibili, avvisi #8 FAPI
6/2025 e #10 FAPI 2/2022; frontend e backend health 200. DATE-2 resta pendente:
il campo potrà essere reintrodotto soltanto insieme alla migration completa.

## ✅ GATE DATE-1 — REGOLE DURATA PROGETTO — 2026-07-31

Verificato lo stato prima di intervenire: UX-5/migration 064 esiste ma tratta
anche i termini come campi liberi; PRJ-2 non è iniziato; B2 copre soltanto
massimali e parametri costo. Backup cifrato fresco verificato:
`/app/backups/gestionale_backup_pre_date1_20260731_140410.sql.zip.gpg`,
SHA-256 `a754cd0beebf21c0ad1ad1208cf1af206307cc315340de8de3487bfbe16f1c58`.

DATE-1 implementato senza migration: nuovo valore JSONB versionato
`durata_termine` su `AvvisoRegola` con tipo termine, ancoraggio, durata
valore/unità, prorogabilità, tassatività e disciplina dello slittamento nei
giorni non lavorativi. Categorie coerenti (`attuazione` o
`rendicontazione`), fonte/articolo obbligatori, correzioni umane validate senza
bypass. Prompt estrattore aggiornato per proporre la struttura senza inventare
ancoraggi. I formati v1 restano compatibili.

Censimento live read-only: 2 progetti (#5/#11), entrambi senza avviso/revisione,
senza date UX-5 qualificate e senza presenze; 0 regole avviso. Nessun termine è
oggi calcolabile e nessun dato è stato modificato. Report:
`audit/DATE_PROGETTO_REPORT.md`.

Gate struttura confermato dall'utente. Il confutatore ha trovato tre bypass:
durata invalida degradata a testo, formato prompt che perdeva
delega/variazioni e approvazione senza rivalidare il JSONB corrente. Correzioni
fail-closed applicate; regressione Avvisi 38/38 e verifica indipendente
Avvisi+B2 49/49 verdi. Verdetto finale confutatore: **OK**, nessun blocker.
DATE-2 autorizzato; in caso di più regole validate sullo stesso termine il
motore dovrà fallire con ambiguità esplicita. Nessun deploy, migration o cambio
DB eseguito in DATE-1.

## ✅ CONVENZIONE NOMINATIVI — 2026-07-31

Applicata la regola unica `COGNOME Nome` e ordinamento alfabetico per cognome
poi nome, insensibile a maiuscole e accenti. Utility condivisa frontend
`utils/personName.js`; query server aggiornate per collaboratori, allievi e
consulenti, con `lower(unaccent())` prima di paginazione/filtri. Migration
Alembic `070` con extension/funzione `unaccent` e indici funzionali, provata su
copia e applicata al DB reale.

Punti coperti: timesheet, calendario, presenze, assegnazioni, collaboratori,
allievi, associati progetto, aziende/referenti, consulenti, preventivi,
dashboard, utenti, documenti mancanti, proposte agenti e fallback contratti.
Report: `audit/NOMINATIVI_REPORT.md`. Censimento: capitalizzazioni storiche in
maiuscolo e record di prova `Codex Runtime Test` id 33; nessuna normalizzazione
dati eseguita.

Verifiche: frontend **41 suite / 327 test / 0 fallimenti**; backend completo
**986 passed / 6 skipped / 0 fallimenti** (33 warning non bloccanti). Backup pre-migration SHA-256
`f27f2a55b0b0a13815c3cc9ab3b6a006e385723a09bbaaf6d0c67b4fe2700471`.

## ✅ FOLLOW-UP UI ELIMINAZIONE AZIENDE — 2026-07-31

Riprodotto il terzo tentativo: lo scenario era B lato UI (handler asincrono
senza stato visibile e errori affidati al toast globale). Ora il click apre un
dialog esplicito con verifica collegamenti, conferma tramite ragione sociale,
stato di avanzamento e messaggi di errore; le aziende non eliminabili mostrano
i collegamenti che bloccano l'operazione. Le azioni della tabella sono raccolte
nel menu contestuale “Azioni”, senza sovrapposizioni.

Sul DB reale, dopo backup verificato, sono state eliminate con audit le aziende
`Azienda 06615351217` (id 4) e `Azienda 97294390584` (id 3). `Ccccc` è bloccata
da 1 membership fondo e 1 associazione progetto; `Maximercato uno srl` da 1
associazione progetto. Il controllo hard-delete resta ADMIN-only; OPERATORE non
vede il pulsante. Frontend ricostruito e container ricreato. Suite: 40 suite /
325 test / 0 fallimenti.

## ✅ DEL-01 / DOC-01 — ELIMINAZIONE AZIENDE E DOCUMENTI — 2026-07-31

Implementate e verificate su DB copia le eliminazioni definitive richieste:
azienda isolata eliminabile da ADMIN con doppia conferma e audit; azienda
collegata bloccata con elenco dei collegamenti; documento di progetto su bozza
eliminabile con rimozione del file fisico; documento su rendicontazione
archiviabile con motivo; RBAC ADMIN/OPERATORE applicato. Dopo l'eliminazione
documentale la versione precedente torna corrente e i dati derivati restano
marcati `fonte_rimossa` per riverifica. Pulsanti e metadati uploader/data sono
presenti nella UI. Migration Alembic `069` applicata al DB reale dopo prova
downgrade/upgrade su copia.

Commit locali: `a22e381`, `52dc15f`, `9f2f9b3`, `03cb9fe` (nessun push).
Backup: `/DATA/progetti/pythonpro_backup_pre_del_doc_20260731_120500.sql.gz`,
SHA-256 `94dd7dc2efc0fa4260ce7423d55961b21e2ce477a6c3be03cf566fa4128a6c59`.
Report: `audit/ELIMINAZIONE_AZIENDE_DOCUMENTI_REPORT.md`.

Dichiarazione finale: **ELIMINAZIONE AZIENDE FUNZIONANTE: SÌ**;
**ELIMINAZIONE DOCUMENTI FUNZIONANTE: SÌ**. Suite backend: **986 passed,
6 skipped, 0 failed**. Frontend: **40 suite, 325 test, 0 fallimenti**.
La copia DB e i file temporanei della prova sono stati rimossi.

> ⚠️ **Due sessioni hanno lavorato su questo branch il 27/07 in parallelo.**
> Questo file è scritto a quattro mani: la sezione "RIPARTENZA" qui sotto
> riguarda l'ondata UX; il resto del file traccia l'altro filone.

## ⏸️ GATE PRJ-5 — ONDATA CORREZIONI PROGETTI E ANAGRAFICHE — 2026-07-31

Eseguiti diagnosi e censimento read-only, senza modificare dati. Backup fresco
verificato: `/DATA/progetti/pythonpro_backup_pre_prj5_20260731_093201.sql.gz`,
SHA-256 `30b8c85f93689cd98fc4460256c5b3959af18632d831d87efcd75e8243deb75c`.

- #5 `poppi`: FAPI 4/2025, nessun documento convenzione disponibile; confronto
  non verificabile, nessuna correzione proposta.
- #11 `MAXI COMMUNICATION` + piano #7: DB collegato a FAPI 2/2025 (ID 6), ma
  entrambi i PDF convenzione riportano FAPI Avviso 6-2025 e codice piano
  `20250611CMIA001`; disallineamento certo.
- Il DB non contiene ancora il record ufficiale FAPI 6/2025. La correzione
  richiede prima ingestione della fonte e poi riallineamento FK progetto/piano.
- Sospetto fallback al primo avviso del fondo **confutato nel codice corrente**:
  parser e conferma non estraggono proprio numero/anno avviso; il dato errato
  deriva dalla bonifica storica NEW-010 che assegnò esplicitamente ID 6.
- Report e query proposte: `audit/PROGETTI_ANAGRAFICHE_REPORT.md`.
- Finding registrato in `audit/FINDINGS_NUOVI.md` come PRJ-5.

**Blocco:** attendere conferma utente progetto per progetto (#11/piano #7 da
correggere verso 6/2025; #5 invariato) e autorizzazione a implementare il fix
applicativo (estrazione esplicita, nessun fallback, mismatch alert, modifica
auditata). PRJ-2/3/1/4/6 non iniziano prima del gate.

### Pulizia avvisi eseguita su richiesta — 2026-07-31

Conservato esclusivamente l'Avviso **#8 FAPI 6/2025** appena caricato; hard-
delete applicativo degli avvisi #1–#7 completato con 7 audit
`avviso_hard_delete`. Poppi (#5) e Maxi (#11), e i piani #4/#7, sono rimasti
senza FK avviso; le stringhe legacy `projects.avviso` sono state azzerate per
evitare riferimenti stale. Zero residui nelle tabelle revisioni/regole/
scadenze/documenti/conoscenze/esiti degli avvisi rimossi.

Backup: `/DATA/progetti/pythonpro_backup_pre_avvisi_cleanup_20260731_101102.sql.gz`,
SHA-256 `dca5390197a333ada17fe5cebacd57e9517a7931388d66bf9f10de810a788691`.
L'Avviso #8 è `bozza`, senza revisione corrente e non ancora collegato a Maxi;
la correzione PRJ-5 resta sospesa fino all'ingestione della revisione ufficiale
e al gate dati.

## ✅ BONIFICA PROGETTI + CALENDARIO — 2026-07-31

Su richiesta utente è stato eseguito un censimento read-only del DB reale:
7 progetti iniziali. Sono stati conservati esclusivamente `poppi` (#5) e
`MAXI COMMUNICATION` canonico (#11); rimossi in una transazione con guardie
gli ID #1, #2, #6, #12 (doppione Maxi) e #13 (fantasma FAPI).

- Backup pre-bonifica verificato:
  `/DATA/progetti/pythonpro_backup_pre_project_cleanup_20260731_083529.sql.gz`
  (`gzip -t` OK; SHA-256 `e2c8f711feb7933cdc7823ea4421f2fe22c798bba1232bf440beed510e96f0e4`).
- Post-bonifica: 2/2 progetti attesi, entrambi attivi; zero riferimenti
  residui in allievi, assegnazioni, presenze, aziende, collaboratori,
  moduli, piani, documenti e tabelle a vincolo RESTRICT.
- Calendario corretto: la legenda ora filtra gli inattivi come la checklist;
  i progetti chiusi compaiono solo attivando “Includi progetti chiusi”.
- Confutatore: frontend 40 suite / 325 test / 0 fallimenti; build esplicita
  e recreate live completati; bundle servito `main.9ebaaa1c.js` contiene il
  filtro `includeClosedProjects`.
- Commit applicativo locale `7632c51`, nessun push. La cancellazione DB è
  già applicata al runtime reale e non è rappresentata da una migration.

## ✅ GATE CHIUSO 2026-07-31 — ONDATA MOBILE / MOB-4

MOB-4 committato e documentato in `audit/MOB4_FORM_REPORT.md`. Form/wizard/
modali censiti secondo la matrice Livelli 1/2/3 già confermata in MOB-0:
guscio full-screen condiviso (`_modal-fullscreen.scss`) per i flussi L1/L2
(Presenze, Area personale, Assegnazioni, e i manager con overlay condiviso);
`DesktopOnlyNotice` per i flussi L3 dichiarati desktop-only (profilo ente,
gestione utenti, piano finanziario, wizard da template, generazione
contratto, upload/parsing FAPI/Fondimpresa, dissociazione forzata).

**Verifiche:** frontend 40 suite/325 test/0 falliti (incl. 4 nuovi su
`DesktopOnlyNotice`); build verde; diff avversariale su
`UserManagement.js`/`GestioneAssociati.js` senza guardie RBAC rimosse.

**Correzione importante trovata dal confutatore**: `docker compose up -d
--force-recreate` da solo **non ribuilda l'immagine**, riusa quella in
cache — il bundle servito dopo il primo tentativo aveva ancora l'hash
pre-MOB-4. Serve `docker compose build frontend` esplicito prima di
`up -d --force-recreate`. Questo mette in dubbio la verifica runtime del
gate MOB-3 chiuso stamattina con lo stesso comando incompleto: il rebuild
vero fatto ora per MOB-4 include comunque tutto lo storico fino a HEAD,
quindi il bundle attuale conferma live **sia** i marker MOB-3 (“Carica
altri”, `--breakpoint-mobile-max`) **sia** quelli MOB-4 — MOB-3 resta
confermato, ma retroattivamente. Dettagli in `audit/MOB4_FORM_REPORT.md`.

**Prossimo:** MOB-5 (vedi roadmap sotto per lo scope non ancora dettagliato).

## ✅ GATE CHIUSO 2026-07-31 — ONDATA MOBILE / MOB-3

MOB-3 committato (`1abafbd`, locale, nessun push) e documentato in
`audit/MOB3_ELENCHI_REPORT.md`.

- Introdotti i componenti condivisi `ResponsiveEntityList`,
  `ResponsivePagination` e `ResponsiveFilters`: una sola fonte dati e una sola
  resa montata per breakpoint.
- Card mobili applicate a collaboratori, allievi, progetti, aziende, ordini,
  preventivi, avvisi, proposte agenti e documenti mancanti; desktop denso
  preservato.
- Ricerca sempre raggiungibile e filtri secondari in bottom sheet mobile con
  contatore/azzera/Back; Calendario e Collaboratori inclusi.
- Paginazione numerica desktop e “Carica altri” mobile con deduplica. Le
  proposte agenti sono limitate a blocchi di 20 su telefono.
- `NEW-046` e `NEW-047` chiusi; `NEW-048` resta onestamente a MOB-6 per
  consolidare Context/lista Collaboratori; `NEW-049` chiuso.

**Verifiche del gate (2026-07-31):**

- Backend completo: **984 passed, 8 skipped, 0 failed** (SQLite isolato locale).
- Frontend completo: **320/321** (39 suite); unico rosso
  `PianoTemplateWizard.test.js` è inquinamento da ordine test già noto,
  confermato riprovando il file isolato: **19/19 verde**. Non è una
  regressione MOB-3 (file non toccato dal commit).
- Build produzione: verde (`main.1adac526.js` locale; il container ricostruisce
  la propria immagine e serve hash diversi ma dallo stesso sorgente
  committato, atteso).
- Runtime ricostruito: `docker compose up -d --force-recreate --no-deps
  frontend` + `docker restart pythonpro_backend`. `/health` 200 su entrambi,
  bundle live `main.61d7625e.js`/`main.eab03e3a.css`, log container puliti.
- Confutatore: diff di `OrdiniManager.js`/`PreventiviManager.js`/
  `AziendeClientiManager.js` (dati economici/PII) senza `console.log` aggiunti
  né guardie ruolo/token rimosse; bundle servito contiene il token CSS
  `--breakpoint-mobile-max` e la stringa “Carica altri”, a conferma che il
  meccanismo responsive è davvero live e non solo nei test.
- **Limite dichiarato**: nessuna verifica Playwright reale in questa sessione
  — `libatk-1.0.so.0` assente anche ora, stesso limite già registrato per
  UX-8/UX-9. La copertura “Playwright reale” del report MOB3 andrebbe
  riverificata quando l'ambiente avrà le lib di sistema; qui sostituita da
  test Jest + verifica bundle/log live.
- Commit `1abafbd`: 40 file, MOB-3 puro frontend, **zero file backend
  toccati**.

**Prossimo:** MOB-4, form, wizard e modali full-screen. MOB-7 e MOB-8
mantengono i gate utente.

## ✅ CHECKPOINT 2026-07-30 — ONDATA MOBILE / MOB-2

MOB-2 è completato e documentato in
`audit/MOB2_NAVIGAZIONE_REPORT.md`.

- Bottom navigation reale per i tre ruoli:
  A/O `Home · Calendario · Presenze · Proposte · Altro`;
  C `Home · Calendario · Persone · Archivio · Altro`.
- `/presenze` è una destinazione operativa che riusa Calendario/API/stato,
  senza logica duplicata.
- “Altro” full-screen ricercabile, focus trap/Escape/Back, voci filtrate dalla
  matrice RBAC unica.
- Header mobile sticky compatto; target navigazione ≥44×44px e safe area.
- Path canonici per 21/21 sezioni, Router SPA, Back/Forward e deep-link
  collaboratore/documenti. `NEW-045` chiuso.
- Layer Livello 1 (Altro, Area personale, presenza, dettaglio proposta)
  chiudibili con Back/gesture.
- Gate browser: admin 21/21, operatore 19/19, consultazione 18/18; zero
  diagnostica browser/API. Desktop verificato a 1280/1440/1920.
- Regressione MOB-1 rieseguita: 4 profili × 21 sezioni + 4 flussi pubblici,
  verde. Frontend 33 suite / 311 test / 3 snapshot; build e runtime verdi.
- Nessun push.

**Prossimo:** MOB-3, componente lista responsive tabella→card e applicazione
alle nove entità previste. MOB-4/5/6/7/8/9 restano successivi; MOB-7 e MOB-8
mantengono i rispettivi gate utente.

## ✅ CHECKPOINT 2026-07-30 — ONDATA MOBILE / MOB-1

L'utente ha confermato il GATE MOB-0 con «procedi» e ha autorizzato il rinvio
esplicito degli scope UX-0/1/3/4 non recuperabili. MOB-1 è completato e
documentato in `audit/MOB1_FONDAMENTA_REPORT.md`.

- Viewport corretto con `viewport-fit=cover`, safe area iOS, radice fluida,
  corpo testo 16px e controlli form mobile `>=16px`.
- Registro breakpoint unico Sass: 480/768/1024/1025; migrate 23 stylesheet e
  rimosse le soglie locali 1120/1180 tramite griglie intrinseche.
- Gate Playwright reale: **4 viewport × (21 sezioni + 4 flussi pubblici)**,
  zero scroll orizzontale; screenshot Home/Calendario/Login prodotti.
- Regressione desktop verificata a 1280, 1440 e 1920px.
- Suite frontend **274 passed**; backend **984 passed, 8 skipped**; build
  produzione verde. Runtime frontend aggiornato, backend e frontend healthy.
- Baseline ripristinata con commit `4d554aa` e `39e690c`; fondamenta e gate
  responsive nel commit `24b5ae5`.
- `NEW-044` mitigato per i nuovi sidecar (credenziali DB redatte); resta aperta
  la bonifica dei sidecar storici e l'eventuale rotazione credenziali.
- Il menu mobile resta alto ma non genera overflow: sostituzione strutturale
  deliberatamente demandata a MOB-2.

**Prossimo:** MOB-2 navigazione mobile, includendo bottom navigation per ruolo,
menu “Altro”, header compatto e correzione di back/gesture + deep-link
`NEW-045`. Nessun push.

## ⏸️ CHECKPOINT 2026-07-30 — ONDATA MOBILE / GATE MOB-0

MOB-0 completato in sola lettura e documentato in
`audit/MOB0_PERIMETRO_MOBILE.md`. **Nessun componente applicativo modificato;
MOB-1 non iniziato.**

### Prerequisiti e verifiche

- Letti stato, ledger SDD, GATE UI v3, findings e ultimi 15 commit.
- Branch locale, nessun push, worktree iniziale pulita.
- Backup fresco
  `gestionale_backup_daily_20260730_020036.sql.zip.gpg` verificato realmente:
  checksum, decrittazione e integrità ZIP OK.
- Censite 21 sezioni applicative: admin 21, operatore 19, consultazione 18;
  aggiunti al perimetro i flussi globali/pubblici login/recovery, portale
  allievi, area personale e notifiche.
- Proposti i tre livelli per singolo flusso, non per intera pagina:
  letture rapide e azioni singole spiegate in Livello 1; consultazione densa e
  CRUD leggero in Livello 2; wizard/import/parsing/configurazioni/bulk e azioni
  ad alto rischio in Livello 3 desktop-only.
- Proposta bottom navigation: A/O `Home · Calendario · Presenze · Proposte ·
  Altro`; C `Home · Calendario · Persone · Archivio · Altro`.

### Finding nuovi

- `NEW-044`: i sidecar JSON dei backup salvano la URL DB completa in chiaro;
  codice non corretto al gate.
- `NEW-045`: back/gesture iOS non ripristina le sezioni e due deep-link
  Collaboratori non sono mappati.

### Blocchi prima di MOB-1

1. Attendere conferma utente del GATE MOB-0.
2. UX-0/1/3/4 restano senza scope recuperabile: vanno definiti e completati,
   oppure esplicitamente rinviati/annullati, prima di toccare gli stessi
   componenti con MOB-1.
3. La baseline completa locale non è verde (7 failure + 241 errori fixture
   startup, confermati preesistenti anche su HEAD pulito): va ripristinata
   prima di usare la suite come gate di non-regressione mobile.

### Ripresa esatta

- Presentare la tabella MOB-0 e attendere le sei decisioni elencate nel report.
- Dopo conferma e risoluzione dei blocchi, partire da MOB-1; nessun lavoro
  responsive deve precedere il gate.

## ⏸️ CHECKPOINT 2026-07-30 — messa in sicurezza pre-Ondata Mobile

Richiesta utente: nuova "Ondata Mobile" (UX mobile/responsive). Regola
dell'ondata: se Ondata UX OPERATIVA è ancora aperta, chiuderla prima (stessi
componenti, rischio conflitto). Verificato: **era aperta**, con 70 file
modificati mai committati (nonostante multipli "DEPLOY VERIFICATO" nelle
sessioni del 27-29/07). Sessione fermata su richiesta utente prima di
scoprire lo scope di UX-0/1/3/4 (vedi sotto). **Non ancora iniziata alcuna
riga di Ondata Mobile.**

### Fatto in questa sessione

1. **Backup fresco verificato**: `gestionale_backup_daily_20260730_020036.sql.zip.gpg`
   (container `/app/backups`, oggi 02:00) prima di qualunque operazione.

2. **Messa in sicurezza dei 70 file non committati** — 6 commit atomici locali,
   nessun push, nessuna perdita (verificato: `git diff --shortstat` tra pre e
   post = 70 file invariati):
   - `2f2dfe0` feat(account): area personale, recupero password, gestione
     utenti admin
   - `3b54971` feat(UX-2): profilo completo ente attuatore (sedi, conti
     correnti, stampa/carta intestata, IBAN mascherato con checksum ISO 13616)
   - `7af5b83` fix(allievi): azienda corrente/sede/progetti nella scheda
   - `97f9810` fix(convenzione): bivio 409 con conferma esplicita di
     destinazione
   - `8edf3ae` test: isola gli startup hook tra fixture TestClient (ux8,
     portale allievi) — pattern non esteso a ux5/ux6/ux6b/ux7 (stesso
     sintomo ma preesistente, confermato anche su HEAD pulito, fuori scope)
   - `9d275f2` docs(status): consolidamento diario sessioni parallele
   - File misti su più feature (`schemas.py`, `apiService.js`,
     `apiService.test.js`) separati per hunk/patch manuale, non a blocchi
     interi, per non mischiare feature diverse nello stesso commit.
   - Verifica: suite mirate 66+69+67 test verdi sui gruppi committati; build
     frontend verde; sintassi Python di tutti i file backend OK.

3. **Suite completa (backend, ambiente locale senza container)**: 737 passed,
   6 skipped, 7 failed, 241 errors. **Confermato con `git stash` che tutti i
   7 failed e la classe di errori (241, pattern "no such table: users" su
   `with TestClient(app) as x` che innesca il bootstrap-utenti prima che le
   tabelle SQLite di test esistano) sono preesistenti anche su HEAD pulito
   pre-commit** — non causati da questa sessione. Non risolti (fuori scope),
   solo documentato dove già toccato (vedi commit `8edf3ae`).

4. **Gate UX-5 (dominio date progetto)**: presentate all'utente le 4
   decisioni di `audit/UX5_GATE_DOMINIO_DATE.md` (2026-07-28) — tutte e
   quattro **confermate**. Durante la verifica è emerso che **UX-5 era già
   stato implementato e committato prima di questa sessione**
   (`aab38cc`/`12edd11`/`3101199`/`0e6cf8e`, migration
   `064_ux5_date_progetto_esplicite.py`), con tutti i 7 CHECK di coerenza,
   validazione presenze W1.5 a warning non bloccante, servizio
   `services/date_progetto.py`, 188 righe di test dedicati. **Migration 064
   già applicata al DB reale** (head reale = `067`, quindi 064 è a bordo da
   prima). Il documento gate era rimasto non aggiornato dopo
   l'implementazione. Le conferme dell'utente coincidono con quanto già
   implementato: **nessun codice da scrivere per UX-5, gate chiudibile**.

5. **UX-0, UX-1, UX-3, UX-4: scope introvabile.** Nessun file nel repo
   (STATUS.md, audit/, docs/superpowers/plans/) li definisce; probabile
   scope dato a voce in una sessione precedente e mai scritto. Ricerca nella
   memoria cross-sessione (`mcp__plugin_claude-mem`) non disponibile (tool
   in errore: `uvx` non trovato) o senza risultati. **Bloccante**: non si può
   implementare uno scope sconosciuto. L'utente ha iniziato a descriverlo
   quando ha chiesto di fermarsi.

### Prossimo passo (ripresa esatta)

1. Farsi ridescrivere dall'utente lo scope di **UX-0, UX-1, UX-3, UX-4** e
   scriverlo qui o in un piano dedicato prima di toccare codice.
2. Decidere se implementarli prima di Mobile (scelta esplicita dell'utente
   in questa sessione: sì, completare l'ondata UX prima) o se, visto il
   costo, rivalutare.
3. Solo dopo, avviare **Ondata Mobile** da **MOB-0** (censimento
   Livello 1/2/3 delle pagine, gate di prodotto da presentare prima di
   scrivere codice) — richiesta completa dell'utente con MOB-0…MOB-9 e gate
   finale, non ancora iniziata.
4. Backup fresco già verificato oggi; rifare backup pre-migration se si
   arriva a toccare schema DB per UX-0/1/3/4.

## ✅ Recupero password + Gestione utenti + Calendario filtri (2026-07-29)

**Un'altra sessione sta lavorando in parallelo su questo stesso branch**
(molti file non miei risultano modificati non committati: `git status
--short` per vedere l'elenco — non toccarli, sono lavoro in corso di
un'altra sessione su password-reset/gestione-utenti/UX-2).

### Fatto e verificato in questa sessione

1. **Recupero password (admin/operatore/consultazione): chiuso.**
   - Root cause reale: `SMTP_PASSWORD` in `.env` non era una App Password
     Gmail valida (48 caratteri invece di 16, Google rispondeva 535
     BadCredentials). Sostituita con una App Password vera generata
     dall'utente per `assistentegestionale@gmail.com`: login SMTP reale
     verificato OK.
   - Secondo bug trovato: `docker restart` NON rilegge le variabili
     d'ambiente di `docker-compose.yml` (solo `docker compose up -d
     --force-recreate` lo fa). `PASSWORD_RESET_URL_BASE` non arrivava al
     container finché non si è fatto recreate.
   - Verificato end-to-end con mail reali (alias Gmail `+operatore`/
     `+consultazione` su `cacciapuotif@gmail.com`): link ricevuti, password
     reimpostate, login riuscito per tutti e 3 i ruoli. Il caso
     "consultazione: link scaduto" era scadenza naturale di 30 minuti, non
     un bug — confermato generando un token fresco e consumandolo subito
     (e verificato che il riuso dello stesso token viene bloccato).

2. **Creazione utenti con ruolo da parte admin: chiuso.**
   - Backend `backend/routers/admin.py`: `POST/GET/PATCH/DELETE
     /api/v1/admin/users`, `POST /api/v1/admin/users/{id}/resend-invite`.
     Account creato con password inutilizzabile + invito via stesso
     circuito del recupero password (mai password in chiaro). Guardie:
     un admin non può disattivare/degradare/eliminare se stesso, né
     l'ultimo admin attivo del sistema (nessuno può farlo). 29 test
     backend verdi (`test_admin_user_creation.py`,
     `test_admin_user_management.py`).
   - Frontend: nuova sezione "🔑 Utenti" (`frontend/src/components/
     UserManagement.js` + `.css`), stile "manager" coerente con
     `CollaboratorManager.css` (card, search/sort, modal conferma). Crea,
     modifica, disattiva/riattiva, elimina, reinvia credenziali. 9 test
     frontend verdi. Deployato live (rebuild+recreate sia backend che
     frontend).

### ✅ Calendario con filtri: CHIUSO (2026-07-29)

Piano completo in `docs/superpowers/plans/2026-07-29-calendar-filters.md`,
tutti gli 8 task fatti e committati (`b4fc2cf`…`1f60601`, poi fix
`20290f4`):

- Task 1 `crud.get_attendances_calendar` (`b4fc2cf`)
- Task 2 endpoint `GET /attendances/calendar` (`d0d1e6d`)
- Task 3 `apiService.getCalendarAttendances` (`ff0312b`)
- Task 4 `calendarFilters.js` stato puro URL+localStorage (`9b13712`)
- Task 5 `CalendarFilterBar.js` (`05554f6`)
- Task 6+7 `Calendar.js` riscritto fetch server-side + legenda dinamica
  (`11a5f1a`)
- Task 8 test performance dataset generato (`1f60601`)
- Piano con checkbox chiusi (`e1a4995`)

**Verifica confutatore (post-deploy, dati reali, non solo unit test):**
rebuild+redeploy backend e frontend, poi tentativo attivo di rompere
l'endpoint reale con curl attraverso il proxy nginx (`localhost:3001`) e
un JWT generato in-process per l'utente `admin` reale (nessuna password
toccata). Trovati e corretti **3 bug reali** non catturati dai test
originali del piano (commit `20290f4`):

1. **RBAC/privacy — grave.** `only_mine=true` per un utente senza
   `collaborator_id` collegato (es. `ui_test_consultazione`) mostrava
   **tutte** le presenze invece di zero: `if collaborator_ids:` tratta
   `[]` come "nessun filtro" (lista vuota è falsy in Python) invece di
   "nessun risultato". Fix: `is not None`. Test di regressione aggiunti
   sia a livello `crud` che endpoint.
2. `collaborator_ids=abc` (non numerico) → 500 invece di 422 (parsing CSV
   manuale senza try/except). Fix: validazione esplicita → 422.
3. `limit` negativo → 500 (`DB_ERROR`, offset/limit SQL invalido) invece
   di 422. Fix: `Query(..., ge=1, le=1000)` / `Query(..., ge=0)`. Nota:
   lo stesso bug esiste anche su `GET /attendances/` esistente (pattern
   pre-esistente nel repo, non toccato — fuori scope).

Non verificato: rendering visivo reale in browser (niente `libatk` /
libs di sistema installabili nel sandbox, no sudo) — copertura sostituita
con verifica end-to-end via HTTP reale (login reale via JWT, dati reali
in Postgres, attraverso il proxy nginx) invece che solo mock Jest.

92 test backend + 8/8 `Calendar.test.js` verdi, build produzione pulita,
nessuna regressione (suite frontend completa ha 1 fallimento
pre-esistente per test-order pollution in `PianoTemplateWizard.test.js`,
confermato presente anche senza le modifiche di questa feature).

Dettagli completi: memoria `pythonpro_calendar_filters.md`.

## ✅ UX-2 FOLLOW-UP — INTESTAZIONE MODIFICA LEGGIBILE (2026-07-29)

- navigazione delle sei sezioni trasformata in pulsanti accessibili;
- layout stabile 3×2 nel modal desktop/tablet e 2 colonne sotto 560 px;
- icona e testo affiancati, testo multilinea non troncato, nessun overflow
  orizzontale;
- stato attivo/completato ad alto contrasto, `aria-current="step"` e focus
  tastiera con outline conforme `#0b5f8a`;
- test modal **2/2** e suite frontend **28 suite, 256 test, 3 snapshot**;
- bundle live `main.41a8d917.js`, CSS `main.7d10a6b6.css`, servizi healthy,
  `/health` 200 e log senza errori;
- confutatore indipendente: **OK FINALE POST-DEPLOY**.

## ✅ UX-2 FOLLOW-UP — MODIFICA ENTE COMPLETA (2026-07-29)

Corretto il disallineamento segnalato tra “Dettaglio” e “Modifica”:

- nella finestra Modifica, la sezione Sede legale mostra ora tutte le sedi e
  consente aggiunta, modifica e disattivazione;
- la sezione Conti correnti mostra i conti con IBAN mascherato e consente
  aggiunta, modifica e disattivazione senza passare dalla scheda Dettaglio;
- dopo CRUD sedi/conti viene aggiornata anche la lista enti, evitando dati
  visivamente stale;
- i selettori delle sezioni vanno a capo e rendono chiaramente raggiungibili
  Legale rappresentante e Note & Logo;
- nel Dettaglio il legale rappresentante è sempre presente, le note mostrano
  anche lo stato vuoto e il logo viene visualizzato come immagine tramite
  download autenticato, non soltanto come nome file;
- sicurezza invariata: negli elenchi e in modifica gli IBAN restano
  mascherati; nessun form annidato o submit accidentale.

Verifiche:

- test mirati: **2 suite, 6/6**;
- frontend completo: **28 suite, 256 test, 3 snapshot**;
- build produzione e `git diff --check`: verdi;
- bundle live `main.cfbc3fcf.js`, backend/frontend healthy e `/health` 200;
- confutatore indipendente: **OK FINALE POST-DEPLOY**, nessun bloccante.

## ✅ UX-2 ENTI ATTUATORI — DEPLOY VERIFICATO (2026-07-29)

Scheda e dati ente:

- aggiunta una vista di dettaglio autonoma con tab per panoramica, sedi,
  conti correnti e stampa/brand; modifica e consultazione restano separate;
- logo e carta intestata sono indipendenti; la carta intestata accetta
  PNG/JPEG/PDF;
- configurabili margini in mm, dimensione e posizione logo, applicazione
  carta intestata alla prima o a tutte le pagine e piè di pagina;
- anteprima PDF neutra disponibile senza generare un contratto reale;
- aggiunti sito web validato e social estendibili per piattaforma, etichetta
  e URL.

Sedi e conti:

- nuove entità `ImplementingEntityLocation` e
  `ImplementingEntityBankAccount`, con CRUD e disattivazione dalla scheda;
- vincoli DB/applicativi: una sola sede legale attiva, una sola sede
  principale attiva e un solo conto predefinito attivo per ente;
- sedi con tipo legale/operativa/amministrativa/accreditata, contatti,
  estremi di accreditamento e date di attività;
- IBAN italiano/estero validato con checksum ISO 13616, BIC/SWIFT,
  intestatario, banca, agenzia e note;
- IBAN sempre mascherato negli elenchi e nella scheda; consultazione integrale
  esplicita solo per admin/operator e registrata in audit, inclusi i tentativi
  negati; nessun IBAN viene scritto nell'audit;
- il dialogo di generazione contratto permette di scegliere sede e conto;
  default rispettivamente sede legale e conto predefinito.

Documenti e compatibilità:

- contratti, template contratto e nuovi timesheet applicano la configurazione
  dell'ente attuatore del progetto solo quando è esplicitamente abilitata;
- il percorso legacy resta separato: test di parità conferma output
  byte-identico con configurazione vuota/disabilitata;
- i documenti già generati sono file persistiti e non vengono rigenerati o
  modificati;
- migrazione Alembic `067_ux2_implementing_entity_full_profile.py` applicata,
  runtime `067 (head)`;
- backfill live verificato: 2 enti/2 sedi/1 conto, nessun ente senza sede
  legale, nessun duplicato legale/principale/predefinito e nessun IBAN
  invalido.

Verifiche e deploy:

- backup pre-migrazione cifrato:
  `gestionale_backup_pre_ux2_20260729_133801.sql.zip.gpg`; la retention
  automatica ha rimosso il vecchio backup
  `gestionale_backup_emergency_shutdown_20260715_125806.sql.zip.gpg`;
- test backend UX-2: **11/11**, incluso il percorso secondario
  `/projects/{id}/full-context`;
- frontend completo: **27 suite, 254 test, 3 snapshot**;
- build produzione e `git diff --check`: verdi;
- smoke live autenticato: lista/dettaglio/sedi/conti 200, anteprima 200 e PDF
  valido, nessuna esposizione dell'IBAN integrale;
- backend e frontend healthy, `/health` 200; bundle live
  `main.94bf6e44.js` contiene scheda completa, anteprima, consultazione IBAN e
  selettori sede/conto per il documento; log post-deploy senza errori.
- revisione avversariale: chiuso un leak IBAN nel `full-context` tramite
  serializzazione fail-safe globale; smoke live con ruolo consultazione
  conferma legacy solo mascherato, conti con `iban=null` e zero IBAN completi;
- SVG escluso end-to-end dai loghi perché non renderizzabile da ReportLab
  (nessun SVG preesistente nel DB); BIC validato anche in update e intervalli
  data sede validati sullo stato finale persistito;
- confutatore indipendente: **OK FINALE POST-DEPLOY**, nessun bloccante
  residuo.

Pendenti/non inclusi:

- nessun commit e nessun push effettuati;
- due vecchi test end-to-end (`test_e2e_catena_contratto.py` e
  `test_timesheet_snapshot.py`) non partono per un problema preesistente
  della fixture di startup/TestClient che usa una sessione priva della
  tabella utenti; i percorsi modificati sono coperti dai test UX-2 isolati.

## ✅ ALLIEVI + AREA PERSONALE — DEPLOY VERIFICATO (2026-07-29)

Correzione Allievi:

- l'API espone ora azienda corrente, sede e tutti i progetti associati;
- Giovanni Caruso `#4` è visibile con azienda attuale Power Impianti `#10`,
  progetto MAXI COMMUNICATION `#11` attivo e `#12` storico
  (`cancelled`/inattivo);
- il cambio azienda conserva i collegamenti progetto già registrati;
- i nuovi collegamenti sono ammessi solo verso progetti attivi compatibili
  con l'azienda corrente; le selezioni nuove incompatibili vengono rimosse;
- decisione di dominio: viene mostrata una sola **azienda attuale** e tutti i
  progetti, compresi gli storici. Il DB non conserva l'azienda storica per
  ogni partecipazione: per ricostruirla servirebbe una futura tabella
  temporale/snapshot azienda-progetto.

Area personale e amministrazione utenti:

- pulsante profilo sempre disponibile in alto a destra;
- modifica nome, cognome, email e telefono; foto profilo autenticata con
  upload/eliminazione; cambio password;
- avatar limitati a PNG/JPEG/WebP, massimo 2 MB, validati tramite firma reale;
- l'amministratore crea un utente con nome, cognome, email e ruolo; lo
  username viene generato automaticamente e l'utente completa il profilo;
- la propria email non può essere cambiata dal pannello admin: deve passare
  dall'Area personale con conferma password;
- l'interfaccia descrive l'invito come predisposto/in coda, senza dichiarare
  una consegna email non verificata.

Migrazione e deploy:

- aggiunta Alembic `066_add_user_profile_fields.py`; runtime confermato
  `066 (head)`;
- backend e frontend ricostruiti e riavviati; health check live verdi;
- bundle live `main.6eb62e21.js` contiene Area personale e la nuova UI
  Allievi;
- test backend eseguiti in due gruppi: **60/60** e **43/43**;
- frontend completo: **26 suite, 248 test, 3 snapshot**; build produzione
  pulita;
- smoke live: profilo 200, avatar senza auth 401, tipo falso 400, oltre 2 MB
  413, modifica propria email da admin 409;
- `git diff --check` e compilazione Python dei file modificati: verdi;
- confutatore indipendente: **OK FINALE POST-DEPLOY**, nessun blocco residuo.

Pendenti/non inclusi:

- nessun commit e nessun push effettuati;
- lo storico dell'azienda per singolo progetto richiede una futura modifica
  del modello dati;
- la consegna SMTP delle email non è dichiarata risolta: il flusso applicativo
  accoda/predispone correttamente il link, ma il canale Google già censito
  continua a richiedere credenziali valide.

## ✅ FIX LIVE — 409 allegato convenzione MAXI (2026-07-29)

Caso reale: la UI ha inviato
`POST /api/v1/projects/5/confirm-convenzione`, ma il DB conferma che `#5` è
`poppi`; il PDF estrae il codice `20250611CMIA001`, appartenente al canonico
`MAXI COMMUNICATION #11`. Il `409` proteggeva correttamente `#5` dalla
contaminazione e **non è stato rimosso**.

Correzione definitiva:

- l'upload project-scoped esegue il match globale e, se riconosce un altro
  progetto, mostra prima della conferma nome e ID di origine/destinazione;
- l'utente deve premere esplicitamente
  **“Allega a #11 · MAXI COMMUNICATION”**;
- il cambio destinazione usa `modalita=associa`: archivia solo il PDF e non
  aggiorna campi, aziende o collegamenti;
- un `409` correggibile non consuma più la preview; il claim finale è atomico
  (`Redis GETDEL`, `Lock` sul fallback locale), quindi replay/conferme
  concorrenti non possono archiviare due volte lo stesso token.

Verifiche:

- backend UX-6/UX-6b/token: **35 passed**;
- frontend mirato: **12 passed**; suite completa: **25 suite, 237 test,
  3 snapshot**;
- build produzione e `git diff --check`: verdi;
- confutatore finale indipendente: **OK**;
- runtime: backend e frontend healthy, `/health` 200; bundle servito
  `main.779628f9.js` contiene il nuovo bivio;
- smoke live con preview temporanea Redis: `409` su #5 e
  `token_survived_conflict=true`; chiave smoke rimossa, nessun dato reale
  modificato.

Il tentativo dell'utente precedente al fix aveva già consumato il vecchio
token: dopo un refresh completo del browser occorre ricaricare il PDF una
volta, poi scegliere il pulsante esplicito verso `#11`.

Il censimento read-only ha trovato 14 PDF non referenziati nel volume upload,
compreso l'ultimo tentativo. Non sono stati cancellati: alcuni potrebbero
essere legacy recuperabili; eventuale cleanup richiede inventario,
quarantena/TTL e verifica dei riferimenti DB.

File del fix ancora nel worktree, nessun commit e nessun push:
`backend/fapi_preview_store.py`, `backend/routers/convenzione_upload.py`,
test backend dedicati, `frontend/src/components/FapiUpload.js` e relativo test.

## ⏸️ CHECKPOINT — Area personale e recupero password (2026-07-28)

Sessione fermata su richiesta dell'utente **prima del deploy**. Le modifiche
sono ancora nel worktree e non vanno scartate né riscritte da zero.

### Aggiornamento dell'ultimo tentativo di chiusura (22:17)

- Confermato nessun processo `pytest` residuo a fine sessione.
- La password `ADMIN_DEFAULT_PASSWORD` configurata non coincide con quella
  reale (`POST /auth/login` → 401); l'utente ha confermato di non ricordare la
  password admin. Nessuna password è stata forzata o modificata.
- SMTP PythonPro provato realmente: l'account
  `assistentegestionale@gmail.com` è quello configurato, ma sia
  `SMTP_PASSWORD` sia `GMAIL_IMAP_APP_PASSWORD` vengono rifiutate da Google con
  `535 BadCredentials`. Nessuna mail è partita da quel canale.
- Recupero consegnato con successo usando il canale SMTP già configurato per
  gli agenti; il destinatario predefinito è stato confrontato via hash e
  coincide con l'email dell'admin. È stato inviato un link monouso da 30
  minuti, senza stampare destinatario o token. Poiché il deploy non è stato
  ancora eseguito, alla ripresa inviare **un link fresco dopo il deploy**.
- Le copie temporanee protette di `email.json` usate per l'invio sono state
  eliminate; gli originali OpenClaw non sono stati modificati.
- Il confutatore ha trovato un leak P0: `RequestValidationError` includeva
  password/token nel proprio `input`, che finiva nei log tramite
  `exc.errors()` e `ErrorHandler.log_error`. Corretto in `error_handler.py` e
  `main.py`: nei log restano solo campo/tipo, senza input/ctx/traceback.
- Il verificatore ha trovato un secondo leak: `logger.exception` nel sender
  poteva serializzare l'indirizzo dentro `SMTPRecipientsRefused`. Corretto con
  log generico senza eccezione/traceback e test avversariale dedicato.
- Entrambi i revisori hanno riesaminato i due fix e li considerano chiusi.
  Non hanno dato approvazione finale: restano suite completa e runtime.
- Test anti-leak `tests/test_logging_safety.py`: **4 passed**. Il verificatore
  ha eseguito logging + password-reset service: **8 passed** e frontend mirato:
  **35 passed**.
- Suite frontend completa ripetuta: **24 suite, 232 test, 3 snapshot**.
  Build produzione ripetuta con successo:
  `main.c30fa976.js`, `main.9cab4140.css`.
- La suite backend completa (924 test) è stata riavviata su SQLite temporaneo,
  è arrivata almeno all'11% senza failure visibili ed è stata interrotta
  dall'interruzione della sessione. Una suite mirata da 30 test è stata poi
  fermata su richiesta dell'utente dopo 8 test verdi. Nessun test è rimasto
  attivo.
- **Nessun deploy e nessun commit** in questa sessione. Runtime ancora sul
  bundle precedente `main.1f332f0e.js`; OpenAPI live non espone ancora
  change/forgot/reset password.

### Fatto

- Area personale integrata nel cockpit: modifica nome/email e cambio password.
- Il cambio email richiede la password corrente; il cambio password invalida
  access token e refresh token precedenti tramite credential marker.
- I token refresh non possono autenticare endpoint protetti.
- Recupero password implementato con risposta anti-enumerazione, token monouso
  a scadenza 30 minuti, link nel fragment URL, template email HTML/testo e
  schermate frontend “Password dimenticata?” / reset.
- PII sensibili oscurati nei log e negli audit; destinatari non stampati nei
  log del sender.
- L'account `admin` è stato verificato come unico, attivo e con ruolo `admin`;
  l'email reale fornita dall'utente è stata associata. Scrittura limitata al
  solo campo email e registrata come `admin_email_qualified`, con valore
  precedente e nuovo oscurati nell'audit. Password e altri profili non toccati.

### Evidenze già verdi

- Backend mirato Area personale/recovery/sicurezza: **37 passed**.
- Frontend completo: **24 suite, 232 test, 3 snapshot**, nessun failure.
- Build produzione: verde, bundle `main.c30fa976.js`, CSS
  `main.9cab4140.css`.
- `git diff --check`: pulito.
- Suite backend completa su SQLite isolato/seeded: interrotta volontariamente
  al **33%**, senza errori fino a quel punto, quando l'utente ha chiesto di
  fermarsi. Una vecchia suite SQLite concorrente era rimasta attiva: verificato
  che non usasse PostgreSQL e terminata. Nessuna suite lasciata
  intenzionalmente in esecuzione.

### Stato verificatore e blocchi

- P0 iniziale chiuso: un bearer rubato non può più cambiare email senza
  conoscere la password corrente.
- P0 logging Pydantic e leak destinatario SMTP trovati nel secondo riesame:
  corretti e riesaminati positivamente.
- Il verificatore mantiene **NO-OK temporaneo** finché non viene provata la
  consegna tramite il percorso PythonPro post-deploy e completata la verifica
  runtime. Il canale agenti ha consegnato una mail reale; il canale SMTP
  PythonPro resta guasto (`535 BadCredentials`).
- Il deploy invaliderà tutte le sessioni già aperte: prima del riavvio fare una
  prova di login admin oppure garantire prima il recupero con un link fresco.
  L'utente non ricorda la password corrente.

### Ripresa esatta

1. Confermare di nuovo che non siano rimasti processi `pytest`.
2. Eseguire i test mirati Area personale/recovery/logging, poi completare la
   suite backend da 924 test sul DB SQLite isolato.
3. Ricreare backend e frontend; il recupero è la via di accesso perché la
   password admin è dimenticata. Non dipendere dallo SMTP PythonPro finché le
   sue credenziali non vengono sostituite.
4. Smoke test health/OpenAPI/bundle,
   anti-enumerazione e route `/reset-password`.
5. Subito dopo il deploy inviare un **nuovo** link recovery dal canale agenti,
   far scegliere all'utente la password e provare login admin. Non inviare mai
   password in chiaro.
6. Richiamare verificatore e confutatore separati in read-only;
   chiudere solo con entrambi in **OK**.
7. Aggiornare di nuovo questo STATUS e creare commit locali atomici; **mai
   push**.

Residuali non bloccanti già registrati dal verificatore: rate limit recovery
solo per IP, nessun pre-verifica della nuova email, concorrenza token coperta
dal compare-and-swap ma non da un test DB realmente concorrente, tentativi di
reset con token invalido non auditati.

## ▶️ ONDATA UX OPERATIVA — stato al 2026-07-28

### Modo di lavoro concordato con l'utente

> *"parti dal punto 1: quando è verificato e il confutatore dà ok, passa al
> secondo punto e così via."*

Ogni punto si chiude solo dopo una **verifica che prova attivamente a
smentirlo**, non dopo un test che si limita a confermarlo. Esempio reale di
questa sessione: le associazioni del progetto 11 sembravano corrette, ma il
progetto 12 rispondeva identico; solo il confronto riga-per-riga col DB su
quattro progetti diversi (5, 11, 13, 1) ha escluso che l'endpoint ignorasse
`project_id`. Senza quel passo il punto sarebbe stato chiuso a torto.

### ✅ Punto 1 — Attivazione runtime: FATTA E VERIFICATA

Il runtime non gira più su codice vecchio. Comandi eseguiti:

```bash
export DOCKER_CONFIG=/tmp/dockercfg && mkdir -p "$DOCKER_CONFIG"   # /DATA/.docker non è scrivibile
docker compose up -d --force-recreate --no-deps frontend
docker restart pythonpro_backend
```

Confutazione superata su 7 fronti:

| Verifica | Esito |
|---|---|
| Container frontend sulla nuova immagine | `d7902ae0bd8c` → `69f6ca8899f8` |
| Bundle servito | `main.51462523.js` → `main.9c62b80d.js` |
| `/health` e frontend `/` | 200 e 200, entrambi healthy |
| openapi rotte project-scoped | `/projects/{id}/upload-convenzione`, `/confirm-convenzione`, `/fondimpresa/upload-ammissione`, `/upload-riepilogo` presenti |
| `schemas.Project` | espone `aziende_coinvolte` e `allievi_coinvolti` |
| **Dati live vs DB** | prog 5 → 2 az/0 all, 11 → 5/4, 13 → 5/0, 1 → 0/0: **combacia riga per riga**, l'endpoint discrimina davvero per progetto |
| UX-6 non crea gemelli | nessun `db.add(models.Project(...))` nel percorso project-scoped; c'è una guardia 409 se il `codice_fapi` appartiene a un altro progetto |
| Bundle chiama il percorso giusto | `"/projects/".concat(e,"/upload-convenzione")` presente nel bundle servito |

**UX-6 e UX-7 sono ora vivi anche sull'app in esecuzione**, non solo nel codice.

Da sapere per le sessioni future: per interrogare le API live servono
credenziali che **non esistono in chiaro** (le password `ui_test_*` sono random
e non conservate, e `ADMIN_DEFAULT_PASSWORD` in `.env` non corrisponde più
all'utente `admin` reale). Il JWT si genera con la stessa funzione dell'app,
senza toccare il DB:

```bash
docker exec pythonpro_backend python -c "
from datetime import timedelta
from auth import SecurityUtils, User
from database import SessionLocal
db = SessionLocal()
user = db.query(User).filter(User.username == 'ui_test_admin').one()
print(SecurityUtils.generate_token(
    data={
        'sub': user.username,
        'type': 'access',
        'role': user.role,
        'credential_marker': SecurityUtils.credential_marker(user.hashed_password),
    },
    expires_delta=timedelta(minutes=30),
))
db.close()"
```

### ✅ Punto 2 — UX-8 dissociazione: CHIUSO il 2026-07-28

Commit: `99213df` (backend), `dd834a0` (UI), `be8c00f` (findings).

**Scoperta che ha cambiato la specifica.** Lo STATUS precedente dava per buone
guardie su "presenze" e "timesheet". Nel dominio reale **non esistono**:
`attendances` traccia i *collaboratori* e i timesheet pendono da `assignment`,
non da `allievo`. Le uniche tracce di un allievo su un progetto sono la riga
`allievo_project` (`ore_frequentate`, `stato`, `attestato_emesso`) e
`dati_retributivi`. Le guardie sono state ridefinite su questi fatti.

**Decisioni dell'utente** (da non rimettere in discussione):

| Domanda | Risposta |
|---|---|
| Cosa blocca la dissociazione di un allievo | `attestato_emesso` → **blocco assoluto, non forzabile nemmeno da admin**; `ore_frequentate > 0` → blocco **forzabile**; righe in `dati_retributivi` → blocco **forzabile**. `stato` da solo **non** è una guardia. |
| Azienda con suoi allievi ancora sul progetto | **Blocco, nessuna cascata implicita**: 409 con l'elenco degli allievi da staccare prima |
| Il PUT progetto che dissociava in silenzio | **Stesse guardie applicate anche al PUT**, in un servizio condiviso |

**Codice.** `backend/services/dissociazione_progetto.py` tiene le guardie in un
posto solo e non conosce HTTP; `DELETE /projects/{id}/allievi/{allievo_id}` e
`.../aziende/{azienda_id}` sono la via esplicita (forzatura riservata all'admin,
motivo ≥ 10 caratteri, audit su esito bloccato **e** riuscito); il PUT passa
dalle stesse guardie ma **non può forzare**. Sul frontend il pannello
"Associazioni" (`components/GestioneAssociati.js`) elenca aziende e allievi con
l'azione di distacco, mostra i messaggi del 409 e propone la forzatura solo se
il backend la dichiara superabile **e** l'utente è admin.

**Verifiche.**

| Cosa | Esito |
|---|---|
| Suite backend completa (`pytest tests/`, 20 min) | **861 passed, 6 skipped, 0 failed** |
| Delta vs baseline 821 | +39 (`test_ux8_dissociazione.py`) +1 (nuovo in `test_ux7`) — quadra esattamente |
| Suite frontend | **183 passed, 21 suite**; build di produzione verde |
| Mutation check sulla suite | `attestato → forzabile=True` ⇒ **2 test rossi**; file ripristinato |
| Confutazione live | 10 prove su progetti di prova, vedi `audit/FINDINGS_NUOVI.md` |
| Runtime | backend riavviato (rotte UX-8 in openapi), frontend ricostruito, bundle **`main.9c025a26.js`** con `Forza dissociazione` e le DELETE giuste |

La confutazione live è servita costruendo uno stato bloccante ad arte: sul dato
reale tutti gli 8 link hanno `ore_frequentate = 0`, `attestato_emesso = false` e
`dati_retributivi` è vuota, quindi nessuna guardia sarebbe scattata. Due
progetti di prova (14 e 15) creati, usati e **cancellati**: il DB è tornato a 7
progetti e 8 righe `allievo_project`, identico a prima.

La prova che conta: lo **stesso allievo** si stacca senza problemi da un
progetto dove non ha attestato (200) e resta bloccato su quello dove ce l'ha
(409) — la guardia legge il link `(progetto, allievo)`, non l'allievo.

**Limite dichiarato:** nessuna verifica con browser reale (chromium headless
qui è privo di `libatk-1.0.so.0`). La UI è verificata da 10 test jest, dalla
presenza nel bundle servito e dal montaggio in `ProjectManager.js:1516`.

**Due difetti nuovi, registrati e non corretti** (`audit/FINDINGS_NUOVI.md`):
il 403 sulla forzatura non lascia traccia in audit; `DELETE /projects/{id}` è un
soft-delete che si annuncia come eliminazione e conserva le associazioni.

**Da segnalare:** il progetto **11** (quello bonificato, con CUP e allievi) ha
`is_active = false` mentre il doppione **12** è attivo — l'elenco di default
mostra il doppione e nasconde il buono. Non causato da UX-8, nessuna modifica
fatta.

### ✅ Punto 3 — UX-9 albero allievi per azienda: CHIUSO il 2026-07-28

Commit `9ecf868`, findings `deebe6e`. Decisione dell'utente: **lettura +
selezione nel form**, non solo lettura.

`components/AlberoAllievi.js` raggruppa per `Allievo.azienda_cliente_id` e serve
due scopi con un componente solo: la selezione nel form progetto (al posto delle
due select "scegli → aggiungi → ripeti") e la lettura dentro il pannello
Associazioni di UX-8, dove porta i pulsanti di distacco.

Regola di dominio: spuntare un allievo associa anche la sua azienda; togliere
l'ultimo allievo **non** stacca l'azienda. Stesso vincolo di UX-8 in uscita.

**Difetto trovato e corretto per strada:** il form caricava solo la prima pagina
di `/allievi/` (100) ignorando `total`/`has_next` — oltre il centesimo allievo
ne nascondeva l'esistenza senza dirlo. `caricaTuttiGliAllievi` ora segue le
pagine, si ferma a 2000 e dichiara `troncato`, che l'albero mostra.

| Verifica | Esito |
|---|---|
| Suite frontend | **206 passed, 22 suite** |
| Build di produzione | verde — **ha trovato ciò che i test non vedevano** (setter morti dei select rimossi: `no-undef`) |
| Mutation check | tolta l'auto-associazione dell'azienda ⇒ 1 test rosso; ripristinato |
| Contratto paginazione live | `limit=100` → `total=4, has_next=false`; `limit=2` → pagina 1 `has_next=true` ids [4,6], pagina 2 `has_next=false` ids [3,5] |
| Bundle servito | **`main.1f332f0e.js`** con albero, gruppo "senza azienda", avviso di elenco parziale, contatore e chiamata paginata |

Backend non toccato: nessun rilancio della suite backend necessario.

### ▶️ DA FARE, in quest'ordine
1. **Conferma GATE UX-5** in `audit/UX5_GATE_DOMINIO_DATE.md`: modello a
   7 date, nessun backfill automatico, migration additiva in due fasi e
   presenze senza date attività = warning strutturato, non blocco.
2. Dopo conferma, implementare **UX-5**
   → UX-0 → UX-1 → UX-2 → UX-3 → UX-4 → gate finale.

Verificato contro il codice il 2026-07-28: UX-5, UX-0, UX-1, UX-2, UX-3 e UX-4
non sono iniziati (nessun `data_avvio_piano` in `models.py`, nessun componente
di vista dettaglio condiviso, nessun router di profilo utente, nessuna entità
Sede/ContoCorrente, calendario senza filtri, collaboratori senza filtro
progetto).

### Ripetizione GATE UX-6 — 2026-07-28

- Prerequisiti riletti: GATE UI v3 già superato; Ondata M non iniziata;
  worktree iniziale pulito; nessun push.
- Backup fresco cifrato:
  `/app/backups/gestionale_backup_ux6_gate_precheck_20260728_140945.sql.zip.gpg`;
  checksum/metadata presenti, decifratura + ZIP `integrity=True`, 110367 byte.
- Censimento DB reale in transazione read-only: 4 piani finanziari, **0**
  progetti con più piani, **0** piani orfani/senza avviso/senza voci, **0**
  duplicati `(progetto, anno, avviso)` o `codice_piano`.
- Il bug storico duplicava `Project`, non `PianoFinanziario`. Il solo nome
  duplicato è `MAXI COMMUNICATION` (11/12); il fantasma è 13.
- Blocco A già applicato e verificato: CUP e 4 allievi sono presenti su 11; le
  righe allievo di 11/12 sono identiche. Blocco B/C ancora aperti.
- Confronto PDF read-only: il file del 13 è un superset del file già sul 11
  (11 vs 7 pagine; testo del corto interamente contenuto nel lungo; Allegato C
  CUP/COR aggiuntivo). Raccomandato riallegare il lungo al progetto 11 tramite
  il flusso UX-6, accettando esplicitamente il conflitto sul documento.
- Stato anomalo corrente: 11 canonico `is_active=false`; 12 doppione manuale
  `is_active=true`; 13 fantasma `is_active=false`.
- Tutte le 14 FK verso progetto censite: su 12/13 restano solo 5 link azienda +
  4 allievi per 12 e 5 link azienda per 13; nessun'altra FK.
- Confutazione: backend UX-6 **15 passed**; frontend **6 passed**; 4 rotte
  project-scoped presenti nell'OpenAPI live; bundle `main.1f332f0e.js`
  allineato. Finding QA non bloccante NEW-040: warning React `act(...)`.
- Decisione utente ricevuta: soluzione reversibile approvata ed eseguita.
  PDF lungo riallegato al progetto 11 tramite API UX-6 (unico conflitto
  `convenzione_file_path`, accettato esplicitamente; hash verificato).
  Progetto 11 riattivato; 12 e 13 `cancelled`/disattivati con motivazione.
  Listing live: 11 visibile, 12/13 nascosti. Nessun record o file eliminato.
- **GATE UX-6 CHIUSO.**

### GATE dominio UX-5 — presentato il 2026-07-28

- Stato verificato: `Project.start_date/end_date` sono ambigui e W1.5 li usa
  oggi come blocco per le presenze; Cockpit usa `end_date` sia come fine
  progetto sia come richiamo alla rendicontazione.
- DB reale: 0 `avviso_regole` e 0 `avviso_scadenze`; non esiste oggi una fonte
  validata per attribuire termini specifici a FAPI/Fondimpresa/Formazienda.
  L'unico avviso completato (FAPI 3/2026) ha markdown pulito incompleto e solo
  due proposte pendenti non pertinenti alle date operative.
- Dati legacy: i 7 progetti non permettono di interpretare onestamente
  `start_date/end_date`; presenze e assegnazioni riguardano collaboratori, non
  provano l'inizio effettivo dell'aula. `data_approvazione` è nulla ovunque.
- Proposto modello `DATE`: approvazione, avvio piano, termine piano, avvio/fine
  attività formative, termine rendicontazione, chiusura effettiva.
- Proposto nessun backfill automatico; migration additiva e reversibile, campi
  nullable per legacy ma obbligatori via API/UI sui nuovi progetti; successiva
  qualificazione manuale prima del drop dei campi legacy.
- W1.5: usare solo date attività; se mancanti, warning strutturato e salvataggio
  consentito; range assegnazione e blocco progetto non-active restano.
- Nessun codice/migration UX-5 scritto. Attesa conferma sulle quattro decisioni
  del GATE in `audit/UX5_GATE_DOMINIO_DATE.md`.

### Fatto nelle sessioni precedenti

| | |
|---|---|
| NEW-039 | Suite era **rossa a HEAD** (6 failed): `757e83c` aveva aggiunto i kwargs `provider=`/`model=` alla chiamata LLM senza aggiornare i doppi di test; il `TypeError` finiva nell'`except Exception` dell'estrattore e passava per "sezione fallita". Chiuso (`8b313d9`). **Nota aperta:** quell'`except` troppo largo, in produzione, maschererebbe un errore di firma come estrazione vuota. |
| Lavoro pendente | Working tree sporco di sessione precedente, committato in 3 commit atomici: `bd41bf5` dedup multi-istanza AgentSuggestion, `166e558` DOM-08/DOM-18 piano congelato (migration 063, già applicata al DB reale), `b65dd0d` NotificationSystem montato via AppRoot. |
| UX-6 | **Chiuso** (`0fcb8a5`, `fcadc1a`). L'atto caricato dentro un progetto creava un gemello: il modale chiamava gli endpoint project-less, il cui confirm fa `db.add(models.Project(...))` senza ricevere `project_id`. Aggiunto il percorso project-scoped (FAPI + Fondimpresa) con diff campo-per-campo e guardia 422 sul documento non riconosciuto. |
| UX-7 | **Chiuso** (`b1c5ae3`). Le associazioni si salvavano ma `schemas.Project` non dichiarava `aziende_coinvolte`/`allievi_coinvolti`, che la scheda legge: sempre `undefined` → "nessun associato" a prescindere dai dati. Corretto anche un N+1 reale su `azienda_ids`. |
| Bonifica UX-6 blocco A | **ESEGUITA sul DB reale** (decisione utente): CUP `G64D26000610003` e i 4 allievi travasati dal progetto 12 al progetto 11, con `stato` e `ore_frequentate` preservati. Nulla distrutto: il 12 è ancora intatto. |

### Baseline al momento dello stop precedente (2026-07-27 ~17:00)

backend **821 passed, 6 skipped, 0 failed**; frontend **173 passed, 20 suite**;
build di produzione verde; alembic head `063`; working tree pulito; ultimo
commit dell'ondata `b1c5ae3`.

### GATE ancora aperti

- **UX-6, blocchi B e C.** Decisione utente: *"blocco A ora, C dopo verifica"*.
  A è fatto; **B e C attendono conferma**. Query pronte in
  `audit/UX6_BONIFICA_PROPOSTA.md`. ⚠️ Il blocco C elimina i progetti 12 e 13, e
  `allievo_project.project_id` ha `ON DELETE CASCADE`: eseguirlo solo dopo aver
  verificato che il travaso del blocco A regga.
- **UX-5** — gate dominio sul modello date, da presentare prima di scrivere codice.
- **UX-7** — nessun recupero dati necessario (le associazioni erano già sulla
  relazione canonica): il gate si chiude con la sola presa d'atto.

### Attenzioni

- **Le sedi operative aziende (`81a9b96`, altra sessione) toccano il territorio di
  UX-2c** (sedi multiple). Decisione utente: proseguire, ma **verificare cosa
  esiste già prima di attaccare UX-2**.
- **Ondata B è ancora aperta**: B6a e B5 fatti; **B1** (scadenze avviso), **B3**
  (checklist documentale) e **B6b** non fatti.
- Lo **scheduler dei backup si è fermato al 2026-07-25** (nessun daily il 26 e il 27).
  Backup manuale verificato di questa sessione:
  `/DATA/progetti/pythonpro_backup_pre_ux_20260727.sql`.
- `progetto_beneficiario` è un **relitto**: 0 righe, nessun riferimento nel codice
  applicativo. Da droppare in un giro di igiene.
- La suite backend completa impiega **15–24 minuti**: prevederlo, non scambiarlo
  per un blocco.

## Stato operativo

- Runtime: backend, frontend, PostgreSQL, Redis e ARQ worker healthy.
- Schema reale: Alembic **`063` head**, verificato con `alembic current` sul
  container il 2026-07-27 sera (template piani 060 + FTS archivio 061 + drop
  relitto legacy_template_id 062 + piano congelato DOM-08/DOM-18 063). Backend
  riavviato dopo 062 per riallineare il modello allo schema (il drop colonna
  dava 500 sui piani finché il processo caricava il vecchio modello).
- Baseline backend: **861 passed, 6 skipped, 0 failed** (al commit `99213df`,
  2026-07-28, 20 minuti di esecuzione).
- Baseline frontend: **206 passed, 22 suite**; build production verde.
- Frontend ridispiegato il 2026-07-28, bundle **`main.1f332f0e.js`** (UX-8 UI +
  UX-9 albero); prima dello stesso giorno `main.9c025a26.js` (solo UX-8).
  Backend riavviato lo stesso giorno per caricare le rotte di dissociazione.
- Ridispiegato in precedenza il 2026-07-27 sera, bundle **`main.9c62b80d.js`**:
  live allineato a UX-6 e UX-7 oltre che ai fix auth, sedi operative e import
  XLSX allievi. Il precedente `main.51462523.js` era costruito ma non servito.
- **RUNTIME ATTIVATO il 2026-07-21**: backend riavviato (carica NEW-030/037,
  rotte `/api/v1/archivio/*` live in openapi); frontend **ricostruito e
  ridispiegato** (`docker compose build frontend` + recreate, bundle
  `main.2f02630a.js` con pagina "Chiedi all'archivio"). Verifica live HTTP sul
  runtime: 3 ruoli → search/chiedi/projects 200; `/archivio-chiedi` servita 200;
  openapi espone `azienda_ids`/`allievo_ids` (NEW-030). Backend LAN-portabile:
  da `192.168.2.41:3001` il bundle punta a `192.168.2.41:8001` (http.js).
  Crawl Playwright browser-level NON eseguito: chromium headless privo di
  librerie di sistema (`libatk-1.0.so.0`) in questo ambiente — verifica ridotta
  a HTTP live + suite + jest (nessun render/console-error capturato).
- V1 archivio avvisi e V2 pipeline ingestione sono chiuse.
- Wave dominio 1 e Wave 2.1 timesheet snapshot immutabile sono chiuse.
- Flusso agenti canonico attivo: collector puro → AgentRun/AgentSuggestion → approvazione umana → apply auditato. Nessun auto-apply.
- `AGENT_DATA_RETENTION_ENABLED=false` resta invariato.
- History Git contiene vecchi `.env`: **MAI push** finché non viene ripulita con procedura dedicata.

## Fix sessione 401 concorrenti — LIVE (2026-07-27)

- Problema osservato da Aziende/Progetti/Allievi: più richieste parallele con
  access token scaduto avviavano ciascuna un refresh. Un singolo refresh
  fallito/rate-limited poteva cancellare i token e lasciare la UI aperta con
  tutti gli endpoint a `401`, bloccando anche il salvataggio delle sedi.
- `frontend/src/lib/http.js`: refresh reso single-flight; tutte le richieste
  concorrenti attendono e riusano la stessa operazione.
- Test regressione sui tre endpoint segnalati: un solo refresh, tre retry `200`.
  Gate mirato `6 passed`; suite frontend `154 passed`, 3 snapshot; build verde.
- Commit locale `0d879a8`; nessun push. Frontend ricostruito e ridistribuito,
  container healthy, bundle `main.37446b75.js`; backend health `200`.
- La sessione browser già invalidata richiede un solo nuovo login; dopo il
  caricamento del bundle aggiornato il problema concorrente non deve ripetersi.

## Fix sedi operative aziende/import XLSX — LIVE (2026-07-27)

- Caso reale: la UI dichiarava salvata la sede `Napoli` di Power Impianti, ma
  `AziendaClienteCreate/Update` non dichiaravano `sedi_operative`,
  `fund_memberships` e `project_ids`. Pydantic ignorava i campi extra, quindi
  il CRUD di sincronizzazione era irraggiungibile e la sede non entrava nel DB.
- Aggiunto contratto write/read completo per sedi e fondi; le risposte lista,
  dettaglio, create e update riespongono relazioni e ID usati dall'import
  allievi. Commit locale `81a9b96`, nessun push.
- Test API create/update/persistenza/listing aggiunti. Gate collegato:
  `45 passed`; sintassi e diff-check OK. Suite totale avviata senza failure nel
  blocco iniziale, poi interrotta perché ridondante e molto lenta sulle fixture.
- Backend riavviato e healthy; OpenAPI live conferma `sedi_operative` sia su
  update sia sulla risposta. Nessuna migration necessaria: tabella già a schema.
- Ripristinata con guardia anti-duplicato la riga persa:
  `Power Impianti srl` (ID 10) → `Napoli` (sede ID 1). L'import XLSX può usare
  esattamente `Power Impianti srl` / `Napoli`.

## Fix 422 import allievi XLSX — LIVE (2026-07-27)

- Dopo il ripristino della sede, il POST `/api/v1/allievi/bulk-import` arrivava
  al backend ma falliva con `422`: le celle data lette da ExcelJS come oggetti
  JavaScript `Date` venivano convertite in una stringa non valida e poi
  concatenate a `T00:00:00Z`.
- L'importatore ora normalizza oggetti `Date`, seriali Excel, date ISO e formati
  italiani `GG/MM/AAAA`, `GG.MM.AAAA`, `GG-MM-AAAA`; date impossibili vengono
  fermate prima dell'invio indicando la riga del foglio.
- Il frontend interpreta anche il formato `details` del gestore errori FastAPI:
  un eventuale 422 residuo mostra riga e campo (l'indice API zero-based viene
  tradotto nella riga Excel, intestazione inclusa) invece del messaggio generico.
- Commit locale `a25ef87`, nessun push. Verifica sul commit pulito: **18 suite,
  161 test, 3 snapshot**, build production verde. Deploy isolato dalle altre
  modifiche locali in corso; container frontend healthy, bundle
  `main.51462523.js`, backend health `200`.

## V5 — ingestione avvisi SBLOCCATA via LLM cloud (2026-07-24)

- Il locale (Ollama 7b su CPU, no GPU) estraeva 0 regole in 23 min → vicolo cieco.
- Provider LLM **anthropic** aggiunto a `ai_agents/llm.py` con override per-agente
  (`757e83c`): estrazione avvisi (documenti PUBBLICI) su cloud, agenti con PII
  restano su Ollama locale. `AVVISO_EXTRACTOR_LLM_PROVIDER=anthropic`,
  `AVVISO_EXTRACTOR_LLM_MODEL=claude-opus-4-8` in `.env` (key non committata);
  compose passa le env a backend/arq_worker (`1070a7f`). `anthropic==0.119.0`
  in requirements (immagine ricostruita).
- Estrazione reale FAPI (rev 7, 11k char): **Opus 4.8 ~90s → 44-48 regole**,
  Sonnet 5 ~74s → 21, locale 7b 23min → 0. Modello scelto: **Opus** (thoroughness;
  costo ~$0,38/avviso, trascurabile al volume reale). Proposte in AgentSuggestion
  → validazione umana → avviso_regole → archivio (sblocca NEW-036).
- Worker gunicorn `TIMEOUT=240` (`c17ae79`): l'estrazione sincrona cloud (~90s)
  superava i 60s → UI in timeout. **Backlog: estrazione asincrona ARQ** (fix
  definitivo; con async il modello lento non blocca la UI).

## Ondata UI-COMPLETAMENTO — CHIUSA, GATE UI v3 SUPERATO (2026-07-21)

Chiuse le 3 eccezioni del GATE UI v2 (piano da template, E2E contratto, Chiedi
all'archivio) con ordine E2 → E1 → E3 → GATE v3. Metodo subagent-driven.
Fonti dettaglio (non ripetere qui): piano `docs/superpowers/plans/2026-07-19-ui-completamento.md`,
ledger `.superpowers/sdd/progress.md`, `REMEDIATION_LOG.md` (sez. 2026-07-21),
report gate `audit/UI_VERIFICA_REPORT.md` (v3) e `audit/E3_GATE_REPORT.md`.

- **Fase E2 — catena contratto (GATE superato):** test E2E fino al PDF + negativi;
  review R0 APPROVE-CON-FIX; sweep RBAC su 12 endpoint file/export. Finding chiusi
  NEW-021…028 (di cui NEW-022/024/025 di sicurezza: contratto/PDF timesheet/
  allegato email erano scaricabili da consultazione). NEW-026 resta admin-only
  per decisione utente.
- **Fase E1 — piano da template (GATE confermato dall'utente):** modello
  `PianoFinanziarioTemplate` + migration 060 (su DB reale) + bonifica relitti +
  seed 3 template reali; massimali con precedenza regola avviso validata (422
  cita l'articolo); endpoint + wizard UI 3 passi + fix review UX. Demo su clone:
  enforcement 422 "rif. Art. 12". Decisioni utente: NEW-032 ereditarietà avviso
  esplicitata in UI; NEW-033/034 API espone voce_codice/macrovoce/anno.
- **Fase E3 — Chiedi all'archivio (GATE dimostrato):** FTS dialect-aware +
  migration 061; endpoint search/chiedi con onestà non negoziabile (retrieval
  vuoto→non_presente senza LLM; citazioni validate server-side; LLM giù→
  degradato); UI 3 stati. Verifica empirica su clone: 10/10 query pertinenti;
  4/4 sinonimiche MISS → **pgvector raccomandato** (non implementato). NEW-037:
  domande in linguaggio naturale a `/chiedi` recuperano 0 risultati (AND dei
  lessemi) → oggi rendono `non_presente`; fix a basso costo, aperto.
- **GATE UI v3 SUPERATO** (codice/suite/demo su clone): matrice pagina×ruolo
  admin 20 / operatore 19 / consultazione 18; flussi 1–8 tutti OK (3 eccezioni v2
  chiuse). Dichiarazione: "TUTTE LE PAGINE COLLEGATE E FUNZIONANTI: SÌ" con
  eccezioni oneste. Review whole-branch: **ONDATA CHIUDIBILE** (nessun blocker
  di codice).

**Aperti a fine ondata (backlog, non bloccanti il gate):** NEW-029 (legacy_template_id
con dati), **NEW-030 (alta, fuori scope: azienda_ids/allievo_ids scartati su
/projects, sync links morto)**, NEW-031 (vista piani navigabile assente), NEW-035
(messaggio dedup), NEW-036 (corpus archivio vuoto in produzione), NEW-037 (query
NL su /chiedi), residui v2 UI-12/13/14/18, NEW-020. Raccomandazione pgvector.

**Decisioni utente (2026-07-21):** (1) Ondata M (manuale) → **NON avviata,
tenuta separata per dopo**. (2) attivazione runtime → **FATTA** (backend
riavviato + frontend ricostruito/ridispiegato; crawl browser non eseguibile
per libs mancanti, sostituito da verifica HTTP live). (3) NEW-037 e NEW-030 →
**FIXATI E CHIUSI** (`a7fa2d1`, `6bdb024`). Backlog residuo: NEW-029/031/035/036,
residui v2 (UI-12/13/14/18, NEW-020), raccomandazione pgvector.

Regole invariate: commit atomici mai push, migration solo Alembic provate su
copia, agenti solo proposte, nuovi problemi in FINDINGS_NUOVI, stop ai GATE.

## Lavoro corrente — programma giro completo

Prompt operativo avviato il 2026-07-17. Sequenza richiesta:

1. Ondata S — fix rapidi sicurezza.
2. V5 — ingestione dei quattro avvisi reali.
3. Ondata B — binding avviso → operatività.
4. Ondata L — case base, FTS, advisor e feedback loop.
5. Ondata C — fondamenta GDPR; CRM solo dopo prerequisito legale esterno.
6. Ondata F — rifiniture e dimostrazione end-to-end.

L'utente ha autorizzato preventivamente i gate tecnici e ha chiesto di non fermarsi per approvazioni. Eccezione: C1 richiede evidenza esterna che informative e LIA siano state predisposte; C2 non può essere attivata inventando tale fatto.

## Ondata S — CHIUSA (dettaglio in REMEDIATION_LOG + STATUS_ARCHIVE)

- S1…S6 chiusi (token firmati, SecurityAuditLog redatti, `.env` sample, HMAC
  WhatsApp, rendicontazione in `services/`, pin dipendenze). Ultimo commit
  applicativo `b335d1d`. Suite chiusura 530 passed. Residui: NEW-012 (worktree
  separata), NEW-013 (monitor performance legacy). Storico completo spostato in
  `STATUS_ARCHIVE_2026H1.md`; questo file resta sintetico (≤200 righe).

## V5 — gate file sorgente (in attesa deposito)

- `imports/avvisi/` contiene solo `README.md`: ingestione dei 4 avvisi reali
  (FAPI 3-2026, Fondimpresa 3/2026 e 4/2026, Formazienda 9/2022 rev.9) **non
  avviata** finché mancano i file. Pipeline prevista: upload → pulizia →
  segmentazione → estrazione LLM per categoria → `AgentSuggestion` (no
  validazione automatica).
- Infrastruttura V5 già pronta e testata (dettaglio in REMEDIATION_LOG):
  disattivazione sicura da Archivio Risorse (`03457e1`) e hard-delete protetto
  con doppia conferma (`d7e710f`, `c9ce6fd`), provato su copia temporanea.
  Nessuna cancellazione definitiva sul DB reale: Formazienda 2/2025 (ID 1)
  resta disattivato in attesa di conferma admin dalla UI.

## Sottosistema A — attività predittive CHIUSO

- ATT-01…ATT-07 completati: playbook versionati, checklist per fase,
  `activity_planner`, `procedure_extractor`, apply umano e `AttivitaEvento` append-only.
- Collector proposal-only e trigger esclusivamente manuali; nessun cron aggiunto.
- API `/api/v1/attivita` registrata con RBAC globale e locale: consultazione legge,
  operatore gestisce attività, solo admin modifica playbook.
- Migration `058` provata su clone con upgrade/downgrade/re-upgrade, dati invariati,
  5/5 tabelle e 5/5 indici; poi applicata al DB reale dopo backup cifrato verificato
  `/app/backups/gestionale_backup_att07_pre_migration_20260718_112650.sql.zip.gpg`.
- Gate mirato ATT: **35 passed**. Suite completa: **568 passed, 3 skipped**;
  gli skip sono i 2 monitor performance NEW-013 e il test PostgreSQL-only DOM-21.
- Il confutatore ha trovato un bypass admin nell'apply generico `playbook_voce`:
  corretto e coperto; verdetto **VALIDATO**, verifica indipendente **100 passed**,
  nessun blocker residuo. Riserve aperte documentate in NEW-014…NEW-017.
- Runtime post-migration: backend e worker healthy, `/health` 200, schema `058` senza drift.
- Evidenze: `audit/ATTIVITA_PREDITTIVE_GATE_2026-07-18.md`; design e piano tracciati
  sotto `docs/superpowers/`. Prossimi sottosistemi predittivi B/C/D richiedono spec separate.

## Ondata UI v1 — sintesi storica

- GATE UI v1 non superato (blocker UI-01…UI-17, poi chiusi al v2); dettagli nel
  report `audit/UI_VERIFICA_REPORT.md` e in `REMEDIATION_LOG.md`.
- Utenti test nel DB reale ancora presenti: `ui_test_admin`, `ui_test_operatore`,
  `ui_test_consultazione`, `ui_test_op_legacy`; password random non conservate.

## Regole di lavoro

- Codice nuovo nei servizi di dominio; vietato aggiungere funzioni a `backend/crud.py` root.
- Commit atomici locali `feat/fix(ID): ...`; mai push.
- Ogni modifica con test; suite completa verde a fine punto/ondata.
- Migration esclusivamente Alembic, prima provata su copia DB con verifica dati e drift.
- Nuovi problemi in `audit/FINDINGS_NUOVI.md`.
- LLM e agenti propongono soltanto; applicazione sempre umana.
- Preservare modifiche preesistenti e usare staging selettivo.

## Prompt di ripresa — copia operativa

Riprendi PythonPro da `/DATA/progetti/pythonpro`. Leggi prima `STATUS.md`, la sezione più recente di `REMEDIATION_LOG.md`, `audit/FINDINGS_NUOVI.md` e gli ultimi 10 commit. Non rifare Ondata S: è chiusa, ultimo commit applicativo `b335d1d`. Non fare push e preserva la worktree separata `.worktrees/email-agent`.

### 1. Ondata V5 — quattro avvisi reali

- Verifica in `/DATA/progetti/pythonpro/imports/avvisi` la presenza di: FAPI 3-2026, Fondimpresa 3/2026, Fondimpresa 4/2026, Formazienda 9/2022 rev.9. Se manca anche un file, fermati indicando il path esatto.
- Per ogni file esegui upload → pulizia → segmentazione → estrazione LLM per categoria → AgentSuggestion. Nessuna validazione automatica.
- Correggi pulizia/segmentazione se il rumore reale rompe la pipeline; test sul caso reale.
- Produci quattro report: regole proposte, confidence media, sezioni problematiche e qualità onesta. Fermati al GATE V5 per validazione UI dell'utente; le ondate successive devono tollerare validazione parziale.

### 2. Ondata B — binding avviso/operatività

- B1: scadenze avviso validate in job, notifiche, Agenda/HomeCockpit e suggestion per tassative senza azione.
- B2: massimali/parametri costo validati alimentano piani con precedenza avviso > fondo > warning; violazioni bloccanti citano articolo/testo.
- B3: regole documentali → proposta checklist additiva → apply umano crea `DocumentoRichiesto`.
- B4: prima GATE design; poi pulizia relitti template, nuova entità versionata `PianoFinanziarioTemplate`, seed da costanti, selezione da avviso e bonifica `Avviso.template_id`. Migration solo su DB copia.
- B5: agente timesheet guard proposal-only, warning default, enforcement separato false; GET generativo timesheet → POST con deprecazione.
- B6: migrazione identità ente/avviso a FK con report non matchati; fix dedup JSON/N+1 certification agent.
- Demo completa su DB copia e GATE Ondata B.

### 3. Ondata L — archivio e apprendimento

- L1: case base privo di PII, FTS PostgreSQL italiano, 10 query reali e gate empirico FTS/pgvector; UI “Chiedi all'archivio” con citazioni obbligatorie e risposta zero-result sicura.
- L2: `avviso_advisor` collector puro con rischi da esiti storici, solo suggestion.
- L3: feedback accept/reject, proposta taratura soglie, few-shot solo regole validate non superate/rifiutate, pattern errori; vietati fine-tuning, PII grezza e auto-apply.
- Demo e GATE Ondata L.

### 4. Ondata C — GDPR e CRM

- C1: basi giuridiche per allievi/referenti/legali rappresentanti, backfill “da qualificare”, report regolarizzazione, allegati tecnici DPIA/registro e retention 5-10 anni per fondo/rendicontazione.
- GATE C1 bloccante: C2 parte solo dopo conferma esterna di informative e LIA marketing B2B.
- C2 dopo conferma: timeline CRM, pipeline commerciale, `opportunity_finder` solo soggetti qualificati, storico partecipazioni/esiti. Demo e GATE C.

### 5. Ondata F — chiusura

- F1 smonta `sprint7.py`; F2 archivia docs e aggiorna documentazione piattaforme.
- F3 demo unica completa su DB copia dall'MD all'advisor/opportunity finder, con evidenze API/UI.
- F4 aggiorna `REMEDIATION_LOG.md` con “GIRO COMPLETO OPERATIVO: SÌ/NO” e riserve oneste.

## Memoria storica

## Ondata Revisione e Cancellazioni — checkpoint DEL-1(a) (2026-07-31)

- Backup fresco verificato prima della diagnosi: `/DATA/progetti/pythonpro_backup_pre_rev_del_20260731_110138.sql.gz`, SHA-256 `bb86b9d13027fa93b961a27aacd48829dd35647413ed2512d63c9f129cfdbbd3`.
- Diagnosi runtime completata senza modifiche al DB reale: hard delete azienda non esiste (nessun endpoint `/permanent`, servizio, matrice, UI, RBAC ADMIN o audit). Esiste solo `DELETE /api/v1/aziende-clienti/{id}` soft-delete (`attivo=false`). Su copia: `/permanent` 404, DELETE esistente 200 con `attivo=false`.
- Censimento preliminare aziende: isolate #3, #4, #11, #12, #13, #14; collegate #1, #2, #10. Matrice completa da estendere a documenti, ordini/preventivi, piani, interazioni e rendicontazione.
- REV-0 read-only: 178 pending totali; 54 orfani `avviso_revisione` dell'assistente `avviso_extractor`, 56 validi. Proposta: stato tracciabile “superato/non più applicabile”, in attesa di conferma.
- Report: `audit/REVISIONE_CANCELLAZIONI_REPORT.md`. **Gate aperto: nessun codice fix ancora scritto.**
- Nuova diagnosi Maxi Communication: `upload-formulario` e `upload-piano-finanziario` non archiviano i file in `project_documents`; non esistono endpoint DELETE documenti. La conferma formulario inserisce sempre nuovi `ModuloFormativo` senza deduplica. PG01 ha tre batch identici (25 righe ciascuno); il set canonico è 3 moduli formativi/40h + 2 propedeutici/20h. Pulizia dati e fix idempotenza sospesi in attesa di confermare quale batch conservare.
- Conferma utente: mantenere il batch moduli delle 11:13. Bonifica eseguita: 50 moduli duplicati rimossi, riferimenti riallineati; piano #7 ripulito a 25 voci (rimossi 25 duplicati senza giustificativi). Migration 068 applicata; formulario e piano recenti archiviati con hash/audit. Fix idempotenza piano/formulario e partecipanti derivati dal DB. Confutatore finale **VALIDATO** con HTTP 200: PG01 3/40h formative + 2/20h propedeutiche, 4 partecipanti derivati, documenti formulario/piano presenti, zero FK orfane. Restano non bloccanti UI `utente #N`/solo Scarica (DOC-1/DOC-3).

- Storico precedente completo: `STATUS_ARCHIVE_2026H1.md`.
- Decisioni/verifiche dettagliate: `REMEDIATION_LOG.md`.
- Findings: `audit/FINDINGS_NUOVI.md`.
- Analisi guida: `audit/ANALISI_ARCHITETTURA_2026-07-17.md`.

## 2026-08-03 — Sede di erogazione per azienda: CHIUSA

- Causa della UI vecchia provata: lavoro 071 non committato e non distribuito;
  un rebuild successivo aveva pubblicato accidentalmente il dirty worktree,
  mentre una scheda browser continuava a usare il bundle precedente. Un solo
  componente Delivery (`ProjectManager`) serve sia Nuovo sia Modifica.
- Lavoro preesistente salvato in `7d5f8e1`; modello corretto e UI multi-sede in
  `3ddded2`; collaudo UI `c173eeb`; fix PostgreSQL emerso dal collaudo reale in
  `45cc01b`. Nessun push.
- Migration 072: tabella `project_azienda_delivery_sedi` N-per-link, vincoli
  azienda/ente, migrazione automatica valori 071, FK rendicontazione su
  presenze e snapshot sede sui timesheet. Provata su clone 071, poi applicata
  al DB reale. Backup: `database_backups/pre_072_20260803_115846.dump`, SHA-256
  `59e76914be0bc53c0cd5ee2ac5d016d43e95976481a4cf0b318eebdf6042e5e0`.
- Campi piatti `sede_aziendale_*` eliminati dal passo Delivery ma conservati
  per i placeholder dei contratti. Unico record reale valorizzato: progetto #5
  `poppi`; non riconducibile con certezza perché le aziende collegate non hanno
  sedi censite, quindi conservato e segnalato, non migrato arbitrariamente.
- UI: azienda → sedi → allievi; più sedi, optgroup azienda/ente con indirizzo,
  aggiunta/rimozione, creazione sede anagrafica al volo, checkpoint aziende
  senza sede, touch target 44px e nessun overflow a 375px.
- Downstream: presenza seleziona la sede (auto se unica, obbligatoria se più di
  una); calendario, report timesheet JSON/CSV, PDF e snapshot riportano la
  sede. Non esiste un generatore attestati nel runtime; il portale espone solo
  il flag/link. Regole avviso validate su sede/accreditamento nel DB reale: 0.
- Progetto reale #11 MAXI COMMUNICATION: otto casi su otto PASS con browser
  admin e nuovo context pulito. Evidenze in
  `test-results/delivery-sites-real/` (ignorate da Git).
- Gate: test dominio 15/15, frontend 329/329, build production verde; suite
  backend completa **1018 passed, 6 skipped, 0 failed**.
- Stato finale: **SEDE DI EROGAZIONE PER AZIENDA FUNZIONANTE DALL'INTERFACCIA: SÌ**.

## 2026-08-03 — Scheda, template e modello azienda: CHIUSO

- Specifica canonica unica `backend/services/azienda_field_spec.py` (versione
  `2026-08-03.1`): 50 campi azienda e fogli relazionali `Sedi`, `Conti`,
  `Fondi`. Scheda, template, importatore ed export consumano la stessa
  specifica; test permanente anti-divergenza incluso.
- Migration 073 applicata al DB reale dopo upgrade/downgrade/upgrade su clone:
  completa le sedi operative e crea i conti correnti azienda. Backup
  `database_backups/pre_073_azienda_alignment_20260803.dump`, SHA-256
  `b4019362fa4f5c7117a78e117862f2b75c49b1c57b550eedebccbef776da772a`.
- Nuovo Excel: `Istruzioni`, `Aziende` (50 colonne), `Sedi` (11), `Conti`
  (9), `Fondi` (5), oltre al foglio nascosto `Valori`; intestazioni,
  istruzioni, esempio e dropdown. Il formato legacy a cella pipe resta
  accettato con avviso di deprecazione.
- Import guidato con anteprima create/update/scarti, errori italiani per
  foglio-riga-colonna, nessun nome segnaposto, report CSV; upsert su Partita
  IVA e sincronizzazione idempotente delle entità collegate. Export completo
  e reimportabile.
- Scheda read-only separata dalla modifica, sezioni logiche, valori vuoti `—`,
  sedi/conti/fondi/progetti, IBAN mascherato e reveal auditato per ruoli
  autorizzati. Nessuna relazione documenti specifica azienda esiste nel
  modello: la sezione lo dichiara esplicitamente. Mobile 375 px senza overflow,
  sezioni collassabili e touch target almeno 44 px.
- Collaudo live admin: template UI scaricato; due aziende e tre sedi importate;
  reimport 0 create/2 update/0 scarti; scheda leggibile con tre sedi; export UI
  reimportabile 0 create/15 update/0 scarti; viewport 375/375 e zero target
  sotto 44 px. Evidenze ignorate da Git in
  `test-results/azienda-alignment-real/`.
- Suite: frontend **44/44 suite, 333/333 test**; backend **1020 passed,
  8 skipped, 0 failed**; migration, build production e deploy reali verdi.
- Commit locali: `36baaa1`, `6612171`, `f4bb158`, `52904eb`. Nessun push.

**SCHEDA, TEMPLATE E MODELLO ALLINEATI: SÌ**
