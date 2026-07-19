# Ondata UI — Verifica pagine e collegamenti (BOZZA, lavoro in corso)

Data: 2026-07-19. Stato: UI-1 e UI-2 completati, UI-3 a metà, UI-4 da scrivere.
Questa è la bozza di lavoro: i finding sono verificati, la matrice completa e il
giudizio finale vanno rifiniti al termine di UI-3.

## Metodo (documentato, UI-2)

- Censimento statico: parsing di `App.js` (`SECTION_CONFIG`, navigazione a stato,
  niente react-router), mappa componente→chiamate API da `apiService.js`
  (script in scratchpad, riproducibili), confronto con OpenAPI runtime
  (`GET /openapi.json`, 259 endpoint) e con la policy RBAC di `backend/auth.py`.
- Runtime UI: Playwright headless via docker `mcr.microsoft.com/playwright:v1.59.1-noble`
  (immagine già presente in locale), `--network host --ipc=host`, chromium con
  `--single-process --no-zygote` (senza, crash su questo host ZimaOS).
  Login reale dalla pagina di accesso, click su ogni voce di menu, cattura
  errori console e risposte HTTP ≥400, screenshot per sezione.
- Smoke API: ogni endpoint GET usato dalle pagine chiamato con i 3 ruoli
  (admin/operatore/consultazione) su utenti di test dedicati.
- Flussi con scrittura (UI-3): catene API su backend di copia
  (container `pythonpro_backend_uiverifica`, porta 8003, DB `gestionale_ui_verifica`
  clonato via pg_dump). Nessuna scrittura sul DB reale.

## Utenti di test

Creati via script nel DB reale (password random stampate una volta, non salvate):
`ui_test_admin` (admin), `ui_test_operatore` (operatore), `ui_test_consultazione`
(consultazione), `ui_test_op_legacy` (user legacy, unico modo per entrare in UI
come operatore — vedi UI-01). Per riprendere: rieseguire il reset password con lo
stesso script (update hashed_password, vedi STATUS).

## Matrice sezioni (19 voci `SECTION_CONFIG`)

| Sezione (menu) | Componente | Ruoli frontend | admin | operatore(user legacy) | consultazione |
|---|---|---|---|---|---|
| Home | HomeCockpit | admin,user,manager | OK | OK | — (nessun accesso UI) |
| Dashboard | Dashboard | admin,user,manager | OK | OK (metrics admin correttamente nascoste) | — |
| Calendario | Calendar | admin,user,manager | OK | OK | — |
| Timesheet | TimesheetReport+PDF | admin,user,manager | OK (export OK) | carica OK, export → 403 (UI-05) | — |
| Documenti | DocumentiMancanti | admin,user,manager | OK | OK | — |
| Collaboratori | CollaboratorManager | admin,user,manager | OK | OK, ma Scarica doc/CV → 403 (UI-06) | — |
| Allievi | AllieviManager | admin,user,manager | OK | OK | — |
| Progetti | ProjectManager | admin,user,manager | OK | OK | — |
| Aziende | AziendeClientiManager | admin,user,manager | OK | OK | — |
| Catalogo | CatalogoManager | admin,user,manager | OK (vuoto gestito) | OK | — |
| Listini | ListiniManager | admin,user,manager | OK | OK | — |
| Preventivi | PreventiviManager | admin,user,manager | OK (vuoto gestito) | OK | — |
| Ordini | OrdiniManager | admin,user,manager | OK (vuoto gestito) | OK | — |
| Archivio Risorse | ResourceArchive | admin,manager (NO user → UI-07) | OK | manager sì / user no | — |
| Enti Attuatori | ImplementingEntitiesList | admin | OK | non visibile (voluto) | — |
| Agents Dashboard | AgentsDashboard | admin | OK | non visibile (voluto) | — |
| Agenti | AgentsManager | admin | OK | non visibile (voluto) | — |
| Revisione Agenti | AgentSuggestionsReview | admin,user,manager (hidden) | OK | OK via URL diretto (UI-08) | — |
| Template | ContractTemplatesManager | admin | OK | non visibile (voluto) | — |

Crawl admin: 18/18 sezioni caricano senza errori console/rete. Operatore legacy:
13/13 visibili OK. Screenshot in scratchpad (`pw/shots/`).

## Finding

### 🔴 Rotti

- **UI-01 — Ruoli canonici fuori dalla UI.** Il frontend conosce solo i ruoli
  legacy (`admin`,`user`,`manager` in `SECTION_CONFIG`; profili login con
  `expectedRoles ['user','manager']`). L'utente reale `operatore`
  (ruolo canonico, id 2) e qualunque utente `consultazione` NON POSSONO
  ENTRARE: il login client-side risponde "Le credenziali inserite non
  corrispondono al profilo" (verificato a runtime). Consultazione non ha
  nemmeno un profilo di accesso né sezioni con quel ruolo. `/auth/me` restituisce
  il ruolo grezzo dal DB, non normalizzato. Fix non banale (mappa ruoli in
  frontend o normalizzazione in `/auth/me`): decidere al GATE.
- **UI-02 — Pagina Piani finanziari rotta: `GET /api/v1/piani-finanziari/` → 500.**
  `ResponseValidationError`: schema `tipo_fondo` Literal non ammette `fapi` e
  `formazienda` (valori reali post-bonifica NEW-010) e `budget_rimanente ge=0`
  violato dal piano in sforamento (−23.899,68). Colpisce anche AssignmentModal
  (carica piani). Fix = decisione di contratto dominio: al GATE.
- **UI-03 — Assegna/rimuovi collaboratore↔progetto 404. CORRETTO** (commit
  `4b226d6`): endpoint cross-resource registrati solo a radice, frontend chiama
  `/api/v1/...`. Aggiunto alias `/api/v1` + test. Restano irraggiungibili (ma non
  usati da componenti): `GET /collaborators-with-projects/`,
  `GET /collaborators/{id}/assignments/` (solo wrapper apiService morti).
- **UI-04 — `GET /assignments/{id}/timesheet` 500 su alcuni assignment**
  (`timesheet_generator.py:218`, `float / Decimal` su `ore_assegnate`).
  Verificato: assignment 1 → 500, assignment 52 → 200 (dipende dai dati).
  Fix piccolo candidato (cast) — proposto al GATE perché tocca il generatore.

### 🟠 Incoerenti (pagina visibile → azione vietata)

- **UI-05 — Timesheet: bottone "Export CSV" visibile all'operatore ma
  `POST /reporting/timesheet/export` è admin-only** (pattern
  `ADMIN_ONLY_PATTERNS`): 403 a runtime con messaggio grezzo
  "Request failed with status code 403".
- **UI-06 — Documenti collaboratore: bottoni "Scarica/Anteprima" documento
  identità e CV visibili all'operatore ma endpoint `download-documento`/
  `download-curriculum` admin-only**: 403 a runtime (verificato con click).
- **UI-09 — Endpoint cross-resource a radice senza `require_role`**: i path
  storici (`/collaborators/{id}/projects/{id}` ecc.) usano solo
  `get_current_user` → nessun controllo RBAC (anche consultazione può fare POST
  via API). L'alias `/api/v1` introdotto da UI-03 eredita lo stesso
  comportamento. Da uniformare (candidato NEW).
- **UI-10 — `GET /avvisi/{id}/deletion-impact` 403 per operatore** mentre la
  sezione Archivio è visibile ai manager: coerente con hard-delete admin-only,
  ma la UI non nasconde sempre il percorso (da verificare pulsante).

### 🟡 Attrito UX / incoerenze minori

- **UI-07 — Archivio Risorse visibile a `manager` ma non a `user`**, benché per
  il backend siano lo stesso ruolo (entrambi → operatore).
- **UI-08 — "Revisione Agenti" è sezione nascosta**: per l'operatore è
  raggiungibile solo con URL diretto `/agents/review`; l'unico link in-app parte
  dall'Archivio Risorse, che l'utente `user` non vede. Percorso di revisione di
  fatto irraggiungibile per una parte degli operatori.
- **UI-11 — Footer "Documentazione API" hardcoded `http://localhost:8001/docs`**:
  rotto da qualunque host diverso dal server; esposto a tutti i ruoli.
- **UI-12 — Messaggi 403/errore grezzi** ("Request failed with status code 403")
  invece di spiegazioni operative.

### 🟢 Cosmetici / igiene

- **UI-13 — Pagine orfane** (componenti esistenti mai raggiungibili, nessun
  import): `AgenzieManager`, `ConsulentiManager`, `ProgettoMansioneEnteManager`,
  `CalendarSimple`. I relativi endpoint backend (`/agenzie`, `/consulenti`,
  `/project-assignments`) esistono e rispondono: funzionalità senza UI.
- **UI-14 — Wrapper apiService morti** (`getCollaboratorsWithProjects`,
  `getAssignmentsByCollaborator` e altri non importati da alcun componente).

## UI-3 Flussi trasversali — stato parziale (su backend copia :8003)

1. **Avviso MD → estrazione → regole**: upload+ingest OK (201, revisione creata);
   estrazione LLM eseguita ma `gruppi_totali 5, gruppi_falliti 5, regole_proposte 0`
   sul MD di prova → DA INDAGARE alla ripresa (perché falliscono i gruppi?
   ollama attivo, run `completed` senza errore).
2. **Piano da template**: la feature template (B4) NON esiste — creazione piano
   manuale OK (201, aggancia da avviso `avviso_pf_id` automaticamente dal
   progetto). Massimali per voce: da riprovare col payload corretto
   (`piano_id` richiesto nel body oltre che nel path).
3. **Progetto → collaboratori → checklist → approvo**: OK end-to-end post-fix
   UI-03 (assegnazione 200, documento richiesto creato, upload, validazione da
   operatore 200 con `validato_da` obbligatorio).
4. **Collaboratore incompleto → agenti**: creazione richiede anche
   `fiscal_code` (stringa obbligatoria — 400 se assente: nota UX). Run
   `data_quality` e `contract_agent` OK (proposal-only). Apply-fix su
   suggestion non strutturata correttamente rifiutato (400) — comportamento
   corretto post NEW-005.
5. **Presenze → timesheet**: guardie reali funzionano (presenza fuori periodo
   progetto → 400 con messaggio chiaro; fuori periodo assegnazione → 400).
   Generazione PDF timesheet OK su assignment con dati sani; unlock con motivo
   OK (`sbloccato_da` tracciato). Resta UI-04 su altri assignment.
6. **Agenti review → approva → effetto**: parzialmente coperto (apply su
   suggestion `field_update` da completare alla ripresa).
7. **HomeCockpit card → pagina giusta**: da completare (click card verificato
   solo in superficie).
8. **"Chiedi all'archivio"**: NON ESISTE (Ondata L mai eseguita). Impossibile
   verificare; il manuale (cap. 9) non potrà descriverla. Lo stesso vale per il
   CRM (cap. 8): Ondata C2 mai eseguita.

## Fix applicati

- `4b226d6` fix(UI-03) — alias `/api/v1` assegna/rimuovi collaboratore-progetto + test.

## Da fare alla ripresa

1. Chiudere UI-3: F1 indagine gruppi falliti estrazione; F2 massimali con
   payload corretto; F6 apply field_update con verifica effetto; F7 cockpit
   card-by-card; poi teardown copia.
2. UI-4: rifinire questo report (matrice finale, severità, dichiarazioni) e
   fermarsi al GATE UI.
3. GATE: decidere fix maggiori (UI-01 ruoli, UI-02 schema piani, UI-04 cast,
   UI-05/06 nascondere azioni per ruolo, UI-09 RBAC endpoint radice).
