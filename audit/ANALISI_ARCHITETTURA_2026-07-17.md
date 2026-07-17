# Analisi profonda piattaforma PythonPro — 2026-07-17

> Analisi architetturale (Claude). Parte 1: architettura, flusso target, ridondanze.
> Parte 2: motore di apprendimento, CRM, sicurezza infosec + GDPR.

---

# PARTE 1 — Architettura, flusso target, ridondanze

## Verdetto

Architettura di fondo **buona e disegnata bene** nelle due colonne portanti (piattaforma agenti + archivio avvisi versionato). Ma il giro target **oggi funziona solo a metà**: le due colonne non sono ancora collegate tra loro né al motore operativo (piani, contratti, timesheet). Più uno strato di residui legacy da bonificare.

## 1. Valutazione flusso target, passo per passo

**① Carico avviso ente erogatore in MD → capisce logica** — ✅ **FATTO (V2)**
Pipeline completa: upload MD → pulizia → segmentazione → estrazione LLM per categoria → AgentSuggestion → apply umano che materializza `AvvisoRegola`/`AvvisoScadenza` validate. Modello dati eccellente: revisioni versionate, stati proposta/validata/superata, vincoli DB forti (`ck_avviso_regole_validazione_completa`), confidence, riferimenti articolo/pagina, sha256 anti-duplicato. Manca solo V5: i 4 avvisi reali **non ancora ingeriti**.

**② Capisce scadenze** — ⚠️ **ESTRATTE MA NON USATE**
`AvvisoScadenza` vive solo dentro il modulo avvisi. Nessun consumo fuori da `crud_avvisi`/`suggestion_apply`. Il job `jobs/check_scadenze.py` notifica **solo** scadenze `DocumentoRichiesto`, ignora quelle avviso. Scadenza tassativa di presentazione validata nel DB = nessun avviso a nessuno.

**③ Capisce documenti da produrre** — ❌ **MANCA PONTE**
`AvvisoDocumento` è archivio dei file *dell'avviso* (vademecum, allegati), non "documenti da produrre". Le regole categoria `presentazione`/`rendicontazione` possono contenerli, ma nessuna logica li trasforma in checklist `DocumentoRichiesto` per progetto/collaboratore.

**④ Capisce quale template piano finanziario** — ❌ **NON ESISTE**
Struttura piano hardcoded: `VOICE_TEMPLATES` unico in `piano_finanziario_config.py`, limiti per fondo in `MACROVOCE_LIMITS_BY_FONDO` + tabella `MassimaleFondo` (fondo, anno). Nessuna selezione guidata da avviso. Peggio: `Avviso.template_id` punta a `ContractTemplate` (template *documenti*), e la migration 010 ha agganciato `piani_finanziari.template_id` → `contract_templates` — design confuso, ora relitto (`legacy_template_id`, e `crud.py:810` **scarta silenziosamente** `template_piano_finanziario_id` in input). Le regole `massimali`/`parametri_costo` estratte dall'avviso non alimentano né creazione piano né `_validate_massimale_voce`.

**⑤ Inserisco collaboratore + attività su progetto** — ✅ **SOLIDO**
`Collaborator` → `Assignment` (ruolo, modulo formativo, materia, ore, tariffa, date, tipo contratto, guard anti-overlap) → `Attendance` → link a `VocePianoFinanziario`. Catena completa, indici giusti, fix DOM Wave 1 applicati.

**⑥ Agenti capiscono documenti mancanti per contratto** — ✅ **FUNZIONA, ma cieco all'avviso**
`contract_agent`: tutti i `DocumentoRichiesto` obbligatori validati → suggestion `contract_ready` → apply umano → generazione. `mail_recovery` sollecita i mancanti via bozza email. Però: set documenti obbligatori **manuale per collaboratore**, non derivato dall'avviso. E `DOCUMENTI_OBBLIGATORI_DEFAULT` (contract_agent.py:20) è **costante morta**, mai letta.

**⑦ …e per timesheet** — ❌ **NESSUN CONTROLLO**
`timesheet_generator` + router generano da assignment+presenze senza verificare prerequisiti documentali/contratto firmato. Wave 2.1 ha messo snapshot+lock (bene), ma nessun agente presidia il timesheet.

**Sintesi: cervello (avvisi) e braccia (operativo) costruiti bene, spina dorsale che li collega assente.** Coerente con roadmap dichiarata (V3 ricerca, V4 `avviso_advisor`, V5 ingestione reale) — il pezzo mancante è progettato, non dimenticato.

## 2. Architettura — giudizio

**Punti forti**
- Piattaforma agenti post-remediation: registry dichiarativo unico, collector puri senza scritture, persistenza solo via `run_agent_workflow`, human-in-the-loop obbligatorio, kill switch, audit. Disegno da manuale.
- Archivio avvisi versionato con validazione umana vincolata da constraint DB.
- RBAC centralizzato all'`include_router` (main.py:240-244).
- Parser organizzati per fondo (`services/parsers/fapi/`, `fondimpresa/`).

**Punti deboli**
- **Monoliti root**: `crud.py` 5.614 righe / 228 funzioni, `models.py` 2.541, `schemas.py` 1.813. Tutto import piatto senza package. Ogni dominio (avvisi a parte) passa dallo stesso file. Rischio merge/regressione alto.
- **`routers/sprint7.py`**: grab-bag legacy — generazione contratto + certificazione + magic-link allievi con nome da sprint. Duplica trigger agenti (`/agents/contract-generator/run`, `/agents/certification/run`) accanto a `routers/agents.py`.
- **Doppia identità ente/avviso**: `Project.ente_erogatore`+`Project.avviso` stringhe accanto a `avviso_id` FK; idem `ContractTemplate.ente_erogatore`/`avviso`. Migrazione a FK incompleta = rischio disallineamento.
- `GET /assignments/{id}/timesheet` **genera** (side effect su GET).
- `certification_agent`: dedup con `payload.contains(str(project.id))` — substring match fragile (progetto 1 matcha 11, 21…); `hasattr(models, 'AllievoProject')` inutile; N+1 query nei collector.

## 3. Ridondanze e codice morto

| Cosa | Dove | Azione |
|---|---|---|
| Modulo orfano | `rendicontazione_generator.py` — zero importatori | rimuovere o wire-are |
| Script orfano | `add_assignment_to_attendance.py` in root | spostare in `scripts/` o eliminare |
| Costante morta | `contract_agent.py:20` `DOCUMENTI_OBBLIGATORI_DEFAULT` | eliminare |
| Shim parser legacy | `services/{convenzione,piano_finanziario,formulario}_parser.py` | usati solo da `scripts/backfill_project11_...` one-off → fix import, eliminare shim |
| Requirements triplicati | `requirements.txt` + `_local` + `_simple` con versioni **divergenti** (fastapi 0.104 vs ≥0.110) + `pyproject` | unificare, drift pericoloso |
| Colonne relitto | `piani_finanziari.legacy_template_id`, `legacy_avviso_id`, `template_id→contract_templates`; `crud.py:810` scarta input | migration pulizia |
| Test doppia sede | 8 `test_*.py` in root backend + `tests/` | consolidare in `tests/` |
| Docs stratificati | `docs/` 26 file, audit sovrapposti 2026-04; `STATUS.md` **6.684 righe** (è log, non status) | archiviare, troncare |
| CLAUDE.md errato | dice "piattaforma educativa Python" — è un ERP formazione finanziata | correggere |

## 4. Cosa serve per chiudere il giro (priorità)

1. **V5 + V4 già in roadmap**: ingerire i 4 avvisi reali, poi `avviso_advisor`.
2. **Ponte regole→operativo** (il vero anello mancante, candidata "Ondata Binding"):
   - `AvvisoScadenza` validate → `check_scadenze` + notifiche/agente scadenze;
   - regole `massimali`/`parametri_costo` → alimentano `MassimaleFondo`/validazione voci per revisione collegata al piano (FK `avviso_revisione_id` su piano **esiste già**);
   - regole `presentazione`/`rendicontazione` → generano checklist `DocumentoRichiesto` per progetto/collaboratore. Così contract_agent + mail_recovery diventano avviso-aware **gratis**.
3. **Template piano proprio**: entità `PianoFinanziarioTemplate` (per fondo/avviso) al posto di hardcoded + link improprio a `contract_templates`.
4. **Agente prerequisiti timesheet** (documenti + contratto firmato prima di generare).
5. **Bonifica** tabella §3 + smontare `sprint7.py` + spezzare `crud.py` per dominio (graduale).

---

# PARTE 2 — Motore di apprendimento, CRM, Sicurezza

## A. Motore che apprende da avvisi e documenti

**Insight chiave: i segnali di apprendimento esistono GIÀ nel DB.** Non serve ML/fine-tuning — serve un layer di retrieval sopra dati validati. Quattro miniere già pronte:

| Segnale | Dove | Cosa insegna |
|---|---|---|
| Regole validate + `nota_revisione` | `AvvisoRegola` | estrazioni corrette vs corrette-a-mano = esempi etichettati |
| Decisioni umane | `AgentReviewAction` (action, notes, `result_success`) | quali suggerimenti accettati/rifiutati e perché |
| Esiti reali | `AvvisoEsitoProgetto` (approvato/decurtato/controdedotto + importi) | **il segnale d'oro**: cosa ha funzionato in rendicontazione, dove l'ente ha tagliato |
| Note operative | `AvvisoConoscenza` (tag, riservatezza) | sapere tacito d'ufficio già strutturato |

### Architettura proposta (4 fasi, coerente con roadmap V3/V4/V5)

**L1 — Fascicolo esperienza (case base).** Vista/entità che denormalizza per ogni progetto chiuso: avviso+revisione → regole validate applicate → piano (voci, massimali) → documenti prodotti → esito con decurtazioni. Sopra: ricerca full-text Postgres (`tsvector` italian) su regole/conoscenze/esiti. **GATE V3 (FTS vs pgvector): raccomando partire FTS** — corpus piccolo, FTS gratis e senza infrastruttura; pgvector solo se semantica insufficiente (Ollama locale fa embeddings, upgrade indolore dopo). Prerequisito: V5 — senza corpus il motore gira a vuoto.

**L2 — Agente `avviso_advisor` (= V4 in roadmap).** Collector puro, pattern registry esistente. Su nuovo avviso/progetto:
1. retrieval avvisi simili (stesso fondo/ente, overlap categorie regole);
2. diff regole nuove vs storiche validate (per `categoria`+`chiave`);
3. propone: checklist documenti, scadenze derivate, struttura piano, **rischi da esiti storici** ("avviso simile 2025: decurtazione su delega non autorizzata, vedi controdeduzione X");
4. output = solo `AgentSuggestion`, mai auto-apply.

**L3 — Feedback loop che "educa" gli agenti.** Tre meccanismi, tutti senza toccare pesi modello:
- statistiche accept/reject per `suggestion_type` da `AgentReviewAction` → tarare `confidence` e soglia `needs_careful_review` per agente;
- **few-shot dinamici**: prompt estrattore (già versionati in `ai_agents/prompts/`) arricchiti con 2-3 esempi di regole validate dello stesso fondo — l'estrazione migliora ad ogni avviso validato;
- `nota_revisione` delle regole corrette → tabella "pattern d'errore" consultata dall'advisor.

**L4 (opzionale)** — pgvector se FTS mostra limiti su similarità tra avvisi di enti diversi.

**Anti-pattern da evitare**: fine-tuning (corpus minuscolo, costo alto, opacità), auto-apply degli insight, apprendimento su testo con PII (apprendi da regole strutturate validate, non da documenti grezzi).

## B. Aziende e lavoratori come CRM

**Base dati già da CRM vero**: `AziendaCliente` ricchissima (ATECO, CCNL, dipendenti, matricola INPS, regime aiuti, referente+legale rappresentante con social, sedi multiple, `FundMembership` con storico adesioni fondi, rete `Agenzia`/`Consulente`). Manca il layer relazionale:

1. **Timeline interazioni**: `EmailInboxItem` e WhatsApp esistono ma non collegati ad azienda. FK `azienda_cliente_id` su inbox + entità `InterazioneCRM` (chiamate, incontri, esiti) = storico contatto.
2. **Pipeline commerciale**: stato (lead→prospect→attivo→dormiente), owner, prossima azione. Oggi solo `attivo` booleano.
3. **Collegamento potente col motore A — agente `opportunity_finder`**: nuovo avviso validato → matching regole `destinatari`/`beneficiari` (già categorie di `AvvisoRegola`!) contro ATECO + dimensione + fund membership aziende → propone lista aziende eleggibili con contatti. Stesso pattern suggestion, costo basso, valore commerciale alto. Le regole estratte dall'avviso diventano query di targeting.
4. **Storico partecipazioni** come predittore: `AziendaClienteProjectLink` + esiti → "questa azienda ha già fatto 3 piani Fondimpresa, mai FAPI" → priorità contatto.

Attenzione: punti 3-4 = **profilazione a fini commerciali** — vedi GDPR sotto.

## C. Sicurezza

### Infosec — stato attuale solido

Presenti e ben fatti: JWT con revoca (jti blacklist Redis+fallback), bcrypt, rate limiting, RBAC centralizzato path-based applicato a `include_router`, security headers, request validation (size limit, pattern injection), CORS esplicito, secrets fuori git (solo `.sample`/`.template`; enforcement anti-default su `SECRET_KEY` in `auth.py:28-35`), backup cifrati GPG, kill switch agenti, **LLM locale Ollama** = nessun dato a fornitori esterni.

### Infosec — gap da chiudere

1. **Confronto token magic-link non constant-time** (`portale_allievi.py:41`, `expected == token`): vulnerabile a timing attack. Fix: `hmac.compare_digest`. Verificare anche derivazione del token giornaliero (se deterministico da dati prevedibili, è indovinabile).
2. **Nessun TLS sull'esposizione LAN/ZeroTier** (`http://172.22.0.1:3001`): ZeroTier cifra il tunnel, la LAN no — credenziali in chiaro su `192.168.2.x`. Serve reverse proxy TLS (Caddy/Traefik) prima di uso multi-utente reale.
3. **`.env.development` committato con password** (`dev_password_123`, `dev_redis_123`): accettabile solo se mai riusate altrove; rischio copia-incolla verso produzione. Meglio degradarlo a `.sample`.
4. **`SecurityAuditLog.dati_prima/dati_dopo`** salvano snapshot completi (PII inclusa) in chiaro e senza retention: l'audit log diventa un archivio di dati personali non governato.
5. **Provider LLM `openclaw`**: se endpoint remoto, la pseudonimizzazione regex (`llm_privacy.py`: CF, email, telefono, nomi) è rete a maglie larghe — `NAME_RE` su nomi propri produce falsi negativi garantiti. Con Ollama locale il problema non esiste; con provider remoto, vietare dati collaboratori nei prompt.
6. **`whatsapp` webhook e `portale_allievi` fuori dalla protezione RBAC globale** (by design): verificare firma webhook WhatsApp — non verificata in questa analisi.

### GDPR — stato attuale sopra la media

Esistono: export dati (art. 15) e anonimizzazione (art. 17) collaboratore, consensi con revoca e hash IP, agente `data_retention` che **propone** (non esegue) anonimizzazione, pseudonimizzazione prompt, email solo come bozze approvate.

### GDPR — gap, aggravati dai progetti A e B

1. **`GDPRConsenso` copre solo collaboratori.** Allievi (dati formazione, magic link), referenti aziendali e legali rappresentanti (CF, data nascita, profili social = profilazione ricca) senza base giuridica tracciata. Il CRM del punto B è **illegittimo senza questo**: per marketing B2B verso referenti serve valutazione legittimo interesse documentata (LIA) o consenso, più informativa.
2. **Retention in conflitto con la rendicontazione**: la formazione finanziata impone conservazione 5-10 anni per controlli dei fondi. `data_retention` oggi guarda solo `last_assignment_end` — deve guardare anche stato rendicontazione del progetto e termini di controllo. Retention differenziata per stato, non un solo `RETENTION_DAYS`.
3. **`DatiRetributivi`** (alta sensibilità) consumati da `rendicontazione_generator.py`, modulo **orfano**: dati delicati agganciati a codice morto, senza percorso RBAC chiaro. Da risolvere in bonifica.
4. **DPIA mancante**: agenti LLM + profilazione CRM + matching automatico aziende = trattamento sistematico che rende la DPIA fortemente consigliata (probabilmente dovuta ex art. 35). Nessun registro trattamenti nel repo.
5. **Motore di apprendimento**: se L1-L3 apprendono solo da regole/esiti strutturati (non da documenti grezzi con PII), impatto GDPR quasi nullo. Vincolo di design da scrivere nel piano: **il case base non contiene PII di persone fisiche, solo dati progetto/azienda e importi**.

## Sequenza raccomandata

1. **Fix rapidi sicurezza** (mezza giornata): `compare_digest`, retention audit log, `.env.development`→sample, verifica firma webhook.
2. **V5** (ingestione 4 avvisi reali) — sblocca tutto il resto.
3. **L1 case base + FTS** (chiude anche il GATE V3 con scelta FTS).
4. **V4 `avviso_advisor` + L3 feedback loop** = il "motore che educa gli agenti".
5. **CRM**: consensi/LIA estesi **prima**, poi timeline interazioni + `opportunity_finder`.
6. Trasversale: DPIA + registro trattamenti + retention differenziata rendicontazione.
