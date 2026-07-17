# AUDIT REPORT - PythonPro

> Le evidenze tecniche grezze `FASE_*` citate nel report sono conservate nell'archivio locale protetto `/DATA/progetti/pythonpro-local-archive/2026-07-17_audit_raw` e non sono versionate per ridurre esposizione e rumore del repository.

Data audit finale: 2026-07-05
Progetto: `/DATA/progetti/pythonpro`
Ambito: FastAPI + React + PostgreSQL, uso interno con dati reali e vendita SaaS.

## 1. Executive summary

### Verdetto non tecnico

**a) E' usabile oggi in ufficio con dati reali?**
**No, non senza mitigazioni immediate.** La piattaforma funziona in molte parti operative: in Fase 2 sono stati testati 110 GET e 89 hanno risposto `200` (`audit/FASE_2_funzionale.md:144`), e la suite pytest configurata passa con `115 passed` (`audit/FASE_3_qualita.md:31-33`). Tuttavia ci sono blocchi di sicurezza e governance dati incompatibili con dati reali: segreti in `.env` e backup (`audit/FASE_1_inventario.md:144`; `audit/FASE_6_sicurezza.md:26`), RBAC assente sui router core (`audit/FASE_6_sicurezza.md:28`), logging di header HTTP completi con possibile token (`audit/FASE_6_sicurezza.md:29`), cancellazione GDPR incompleta (`audit/FASE_7_gdpr.md:238`) e audit trail insufficiente (`audit/FASE_7_gdpr.md:240`).

**b) E' vendibile oggi come SaaS?**
**No.** Il blocco primario e' architetturale: non esiste multi-tenancy. Fase 7 ha verificato assenza di `tenant_id`, RLS, schema-per-tenant o DB-per-tenant, e Fase 8 conclude che la readiness shared-SaaS e' `0 tenant production` (`audit/FASE_7_gdpr.md:210-215`; `audit/FASE_8_saas.md:21-25`; `audit/FASE_8_saas.md:221`). Mancano inoltre RBAC tenant-aware (`audit/FASE_8_saas.md:233`), DPA tecnicamente difendibile (`audit/FASE_7_gdpr.md:219-230`), osservabilita operativa (`audit/FASE_8_saas.md:236-237`), restore drill (`audit/FASE_8_saas.md:238`) e zero-downtime (`audit/FASE_8_saas.md:239`).

**c) Le fondamenta sono buone o va ripensato qualcosa di strutturale?**
Le fondamenta tecniche non sono da buttare: FastAPI/PostgreSQL, FK, indici, Docker e alcuni job/backup sono basi utili (`audit/FASE_4_architettura.md:231`; `audit/FASE_8_saas.md:275`). Va pero' ripensato in modo strutturale il modello prodotto: tenancy, autorizzazione, audit trail, ciclo vita dati, deploy immutabile, service layer e gestione agenti AI. La Fase 4 documenta che l'architettura attuale e' ancora da progetto interno, con business logic in router/`crud.py`, commit sparsi, GET con side effect e stato frontend duplicato (`audit/FASE_4_architettura.md:229-231`).

### Numeri chiave

| Metrica | Valore | Prova |
|---|---:|---|
| Finding totali consolidati | 100 | Somma registri Fasi 1-8 in questo report. |
| 🔴 CRITICO | 15 | Conteggio tabella unica sotto. |
| 🟠 ALTO | 38 | Conteggio tabella unica sotto. |
| 🟡 MEDIO | 40 | Conteggio tabella unica sotto. |
| 🟢 BASSO | 7 | Conteggio tabella unica sotto. |
| Endpoint runtime OpenAPI | 239 operazioni su 174 path | `audit/FASE_2_funzionale.md:31`; `audit/FASE_2_endpoint_matrix.tsv` ha 239 righe (`audit/FASE_2_funzionale.md:11`). |
| Decorator endpoint statici | 273 | `audit/FASE_1_inventario.md:26`; differenza statico/runtime `audit/FASE_1_inventario.md:66`. |
| Tabelle DB runtime | 44 | `audit/FASE_1_inventario.md:73`; `audit/FASE_2_funzionale.md:131`. |
| Test backend configurati | 115 passati | `audit/FASE_3_qualita.md:31-33`; output `115 passed` in `audit/FASE_3_qualita.md:293-301`. |
| Copertura test dichiarata | 78,75% su `backend/app`, non sul runtime reale | `audit/FASE_3_qualita.md:33`; problema coverage `audit/FASE_3_qualita.md:73-88`. |
| Copertura reale runtime | NON VERIFICABILE: non misurata su `backend/main.py`, `routers`, `crud`, `models`, `services` | `audit/FASE_3_qualita.md:75-88`; `audit/FASE_3_qualita.md:308`. |
| Vulnerabilita npm | 12 totali: 1 critica, 2 alte, 8 moderate, 1 low | `audit/FASE_6_sicurezza.md:19`; dettaglio `audit/FASE_6_sicurezza.md:74-92`. |
| Vulnerabilita Python | NON VERIFICABILE: `pip-audit`/`safety` assenti, non installati per vincolo read-only | `audit/FASE_6_sicurezza.md:92`; `audit/FASE_6_sicurezza.md:110`. |
| Codice morto stimato, lower bound | 2.862 righe su componenti/file orfani o duplicati verificati | Comando `wc -l` su 5 componenti orfani, `backend/app/main.py`, `reset_password.py`, backup: output totale `2862`; prove orfani `audit/FASE_3_qualita.md:237-256`. |
| Codice runtime duplicato `backend/app` | 1.420 righe Python nella mini-app/strato non runtime corrente | Comando `wc -l backend/app/*.py backend/app/api/*.py ...` -> `1420`; doppia app `audit/FASE_3_qualita.md:128-144`. |

## 2. Registro unico dei finding

| ID | Severita | Area | Descrizione | Prova | Effort | Fase |
|---|---|---|---|---|---|---|
| F1-001 | 🔴 CRITICO | Secrets/config | File `.env` e backup contengono segreti/credenziali runtime. | `audit/FASE_1_inventario.md:144`; `audit/FASE_6_sicurezza.md:26`. | M | 1 |
| F1-002 | 🟠 ALTO | Database/Alembic | DB a head `051`, ma `alembic check` rileva drift schema/modello e fallisce. | `audit/FASE_1_inventario.md:145`; `audit/FASE_2_funzionale.md:84`. | M/L | 1 |
| F1-003 | 🟠 ALTO | Repository hygiene | `.worktrees/email-agent` contiene copia estesa del progetto dentro workspace. | `audit/FASE_1_inventario.md:146`. | S | 1 |
| F1-004 | 🟠 ALTO | Docker/SaaS readiness | `webhook_sink` espone porta host `8099`. | `audit/FASE_1_inventario.md:147`; `docker-compose.yml:274-278`. | S | 1 |
| F1-005 | 🟡 MEDIO | Dependencies | Backend ha 3 requirements divergenti e non un lockfile unico. | `audit/FASE_1_inventario.md:148`; `audit/FASE_1_inventario.md:88-90`. | M | 1 |
| F1-006 | 🟡 MEDIO | Dependencies | Pacchetti backend/frontend non allineati alle latest release. | `audit/FASE_1_inventario.md:149`. | M | 1 |
| F1-007 | 🟡 MEDIO | API inventory | 273 decorator statici vs 239 operazioni runtime. | `audit/FASE_1_inventario.md:150`; `audit/FASE_2_funzionale.md:31`. | M | 1 |
| F1-008 | 🟡 MEDIO | Schema governance | Migration one-shot fuori Alembic restano nel backend. | `audit/FASE_1_inventario.md:151`; `audit/FASE_1_inventario.md:77`. | S | 1 |
| F1-009 | 🟡 MEDIO | Docker parity | Dockerfile runtime e prod divergono su Python, server, npm strategy e porta. | `audit/FASE_1_inventario.md:152`; `audit/FASE_1_inventario.md:122-123`. | M | 1 |
| F1-010 | 🟡 MEDIO | Runtime services | `check_scadenze_scheduler` definito ma non in esecuzione. | `audit/FASE_1_inventario.md:153`. | S | 1 |
| F2-001 | 🟠 ALTO | Listini | I GET principali dei listini vanno in `500` per funzioni CRUD assenti. | `audit/FASE_2_funzionale.md:78`. | M | 2 |
| F2-002 | 🟠 ALTO | Frontend/API contract | `ProjectManager` chiama endpoint beneficiari progetto inesistenti a runtime. | `audit/FASE_2_funzionale.md:79`. | M | 2 |
| F2-003 | 🟠 ALTO | Frontend auth | Diverse pagine usano `fetch` diretto e non inviano Bearer token. | `audit/FASE_2_funzionale.md:80`. | M | 2 |
| F2-004 | 🟠 ALTO | Portale allievi | Pagina pubblica e endpoint profilo sono incoerenti con protezione globale. | `audit/FASE_2_funzionale.md:81`. | M | 2 |
| F2-005 | 🟡 MEDIO | Service frontend legacy | `apiService.js` contiene path non presenti in OpenAPI/runtime. | `audit/FASE_2_funzionale.md:82`. | S/M | 2 |
| F2-006 | 🟡 MEDIO | Admin/performance | Endpoint performance admin esistono ma tornano `503` nel runtime. | `audit/FASE_2_funzionale.md:83`. | S/M | 2 |
| F2-007 | 🟡 MEDIO | Schema/model contract | Modelli SQLAlchemy e DB reale non sono allineati secondo Alembic. | `audit/FASE_2_funzionale.md:84`; `audit/FASE_2_alembic_check.txt:10`. | M/L | 2 |
| F2-008 | 🟡 MEDIO | Frontend build/runtime | Build locale e container frontend non coincidono. | `audit/FASE_2_funzionale.md:85`. | S | 2 |
| F2-009 | 🟡 MEDIO | Codice/API duplicati | Seconda app FastAPI sotto `backend/app/main.py` non e' runtime corrente. | `audit/FASE_2_funzionale.md:86`; `audit/FASE_3_qualita.md:128-144`. | M | 2 |
| F2-010 | 🟡 MEDIO | Frontend dead/hidden pages | Componenti gestionali non importati nella nav/app corrente. | `audit/FASE_2_funzionale.md:87`; `audit/FASE_3_qualita.md:237-256`. | S/M | 2 |
| F2-011 | 🟢 BASSO | Endpoint orfani | Vari endpoint runtime non risultano chiamati dal frontend. | `audit/FASE_2_funzionale.md:88`; elenco `audit/FASE_2_funzionale.md:124`. | S | 2 |
| F3-001 | 🔴 CRITICO | Segreti/codice operativo | Script di reset password admin con password hardcoded e stampata. | `audit/FASE_3_qualita.md:39`; dettaglio `audit/FASE_3_qualita.md:59-69`; `audit/FASE_6_sicurezza.md:27`. | S | 3 |
| F3-002 | 🟠 ALTO | Test coverage | Coverage misura `backend/app`, non runtime reale `backend/main.py`. | `audit/FASE_3_qualita.md:40`; `audit/FASE_3_qualita.md:73-88`. | M | 3 |
| F3-003 | 🟠 ALTO | Logging | Error handler logga header HTTP completi, incluso `Authorization` se presente. | `audit/FASE_3_qualita.md:41`; `audit/FASE_3_qualita.md:90-100`; `audit/FASE_6_sicurezza.md:29`. | S/M | 3 |
| F3-004 | 🟠 ALTO | Complessita | Monoliti e funzioni molto lunghe oltre soglie commerciali. | `audit/FASE_3_qualita.md:42`; `audit/FASE_3_qualita.md:104-126`. | L | 3 |
| F3-005 | 🟠 ALTO | Architettura codice | Doppia applicazione FastAPI con entrypoint incoerenti. | `audit/FASE_3_qualita.md:43`; `audit/FASE_3_qualita.md:128-144`. | M | 3 |
| F3-006 | 🟡 MEDIO | Duplicazione | Renderer contratto duplicato in due router. | `audit/FASE_3_qualita.md:44`; `audit/FASE_3_qualita.md:146-160`. | M | 3 |
| F3-007 | 🟡 MEDIO | Duplicazione | Workflow upload/preview/confirm duplicato nei router FAPI/Fondimpresa. | `audit/FASE_3_qualita.md:45`; `audit/FASE_3_qualita.md:162-172`. | M | 3 |
| F3-008 | 🟡 MEDIO | Separation of concerns | Business logic pesante nei router. | `audit/FASE_3_qualita.md:46`; `audit/FASE_3_qualita.md:174-184`. | L | 3 |
| F3-009 | 🟡 MEDIO | Coerenza REST | Endpoint GET con effetti collaterali o generazione stato/file. | `audit/FASE_3_qualita.md:47`; `audit/FASE_3_qualita.md:186-196`. | M | 3 |
| F3-010 | 🟡 MEDIO | Type safety frontend | Frontend quasi interamente JavaScript senza TypeScript/PropTypes. | `audit/FASE_3_qualita.md:48`; `audit/FASE_3_qualita.md:198-207`. | M/L | 3 |
| F3-011 | 🟡 MEDIO | Test | Test in root esclusi da `testpaths`; coverage non rappresenta tutto runtime. | `audit/FASE_3_qualita.md:49`; `audit/FASE_3_qualita.md:209-221`. | M | 3 |
| F3-012 | 🟡 MEDIO | Tooling | Ruff/mypy configurati ma non disponibili nel container verificato. | `audit/FASE_3_qualita.md:50`; `audit/FASE_3_qualita.md:223-235`. | S/M | 3 |
| F3-013 | 🟡 MEDIO | Codice morto | Componenti frontend presenti ma non importati/usati. | `audit/FASE_3_qualita.md:51`; `audit/FASE_3_qualita.md:237-256`. | S/M | 3 |
| F3-014 | 🟢 BASSO | Logging/debug | `print`, `console.log` e placeholder residui nel codice sorgente. | `audit/FASE_3_qualita.md:52`; `audit/FASE_3_qualita.md:258-270`. | S | 3 |
| F3-015 | 🟢 BASSO | Naming | Convenzioni miste italiano/inglese e path REST eterogenei. | `audit/FASE_3_qualita.md:53`; `audit/FASE_3_qualita.md:272-284`. | S/M | 3 |
| F4-001 | 🟠 ALTO | Transazioni | Confini transazionali frammentati e commit distribuiti. | `audit/FASE_4_architettura.md:35-49`. | L | 4 |
| F4-002 | 🟠 ALTO | Integrita dati | Regole overlap temporale solo applicative, non blindate dal DB. | `audit/FASE_4_architettura.md:52-66`. | M/L | 4 |
| F4-003 | 🟠 ALTO | REST/scalabilita | Endpoint GET con scritture e generazione documenti nel path sincrono. | `audit/FASE_4_architettura.md:68-79`. | M | 4 |
| F4-004 | 🟠 ALTO | Architettura | Service layer incompleto, business logic in router e `crud.py` monolitico. | `audit/FASE_4_architettura.md:81-94`. | L | 4 |
| F4-005 | 🟡 MEDIO | Frontend state | Stato frontend duplicato e non totalmente centralizzato. | `audit/FASE_4_architettura.md:96-111`. | M | 4 |
| F4-006 | 🟡 MEDIO | Flusso progetto | UI progetto ha attriti: beneficiari/regime chiamano endpoint mancanti. | `audit/FASE_4_architettura.md:113-125`; `audit/FASE_2_funzionale.md:79`. | M | 4 |
| F4-007 | 🟡 MEDIO | Performance DB | N+1 query nel riepilogo timesheet per progetto. | `audit/FASE_4_architettura.md:127-137`. | M | 4 |
| F4-008 | 🟡 MEDIO | Scalabilita | PDF/report sincroni limitano scalabilita con 2 worker. | `audit/FASE_4_architettura.md:139-155`. | M/L | 4 |
| F4-009 | 🟡 MEDIO | DB/FK | Alcune FK `CASCADE` possono cancellare storico operativo. | `audit/FASE_4_architettura.md:157-173`; `audit/FASE_4_db_fk.txt:4`. | M | 4 |
| F4-010 | 🟢 BASSO | Indici | Buona copertura indici, ma con ridondanze. | `audit/FASE_4_architettura.md:175-188`. | S/M | 4 |
| F4-011 | 🟢 BASSO | Numerazioni | Numerazione preventivi/ordini ragionevolmente protetta. | `audit/FASE_4_architettura.md:190-201`. | S | 4 |
| AI-01 | 🔴 CRITICO | Integrita dati/LLM | Dati azienda estratti da LLM possono essere applicati anche senza `result.valid is True`. | `audit/FASE_5_agenti_ai.md:111`. | M/L | 5 |
| AI-02 | 🟠 ALTO | Comunicazioni esterne | `mail_recovery` puo' inviare automaticamente email con confidence alta. | `audit/FASE_5_agenti_ai.md:112`. | M | 5 |
| AI-03 | 🟠 ALTO | Documenti ufficiali | Output LLM con confidence alta auto-valida documenti. | `audit/FASE_5_agenti_ai.md:113`. | M | 5 |
| AI-04 | 🟠 ALTO | GDPR/trasferimento dati | Prompt documentale invia contenuti personali/documentali con pseudonimizzazione incompleta. | `audit/FASE_5_agenti_ai.md:114`. | M/L | 5 |
| AI-05 | 🟠 ALTO | Cost control SaaS | Mancano limiti token, budget, cache LLM o rate limit agentico. | `audit/FASE_5_agenti_ai.md:115`. | M | 5 |
| AI-06 | 🟡 MEDIO | Resilienza | Chiamate LLM senza retry/backoff/circuit breaker. | `audit/FASE_5_agenti_ai.md:116`. | M | 5 |
| AI-07 | 🟡 MEDIO | Prompt governance | Prompt hardcoded senza versione, owner, changelog o golden tests. | `audit/FASE_5_agenti_ai.md:117`. | S/M | 5 |
| AI-08 | 🟡 MEDIO | Architettura agenti | Due sistemi di registrazione agenti e percorsi diretti diversi. | `audit/FASE_5_agenti_ai.md:118`. | M | 5 |
| AI-09 | 🟡 MEDIO | Scalabilita | `DataQualityAgent` carica tutti i collaboratori attivi con `.all()`. | `audit/FASE_5_agenti_ai.md:119`. | S/M | 5 |
| AI-10 | 🟢 BASSO | UX/operativita | UI health LLM presente, ma stato runtime non verificato per evitare chiamate esterne. | `audit/FASE_5_agenti_ai.md:120`. | S | 5 |
| SEC-01 | 🔴 CRITICO | Segreti/repository | `.env` reale e backup `.env.bak_*` contengono segreti operativi. | `audit/FASE_6_sicurezza.md:26`. | M | 6 |
| SEC-02 | 🔴 CRITICO | Credenziali hardcoded | Script imposta e stampa password admin hardcoded. | `audit/FASE_6_sicurezza.md:27`. | S | 6 |
| SEC-03 | 🔴 CRITICO | Autorizzazione/RBAC | Router core permettono scritture a qualunque utente autenticato. | `audit/FASE_6_sicurezza.md:28`. | M/L | 6 |
| SEC-04 | 🔴 CRITICO | Logging/token | `ErrorHandler.log_error` registra header richiesta e traceback. | `audit/FASE_6_sicurezza.md:29`. | S/M | 6 |
| SEC-05 | 🟠 ALTO | Sessioni/token frontend | Access e refresh token salvati in `localStorage`; refresh non ruota refresh token. | `audit/FASE_6_sicurezza.md:30`. | M | 6 |
| SEC-06 | 🟠 ALTO | OpenAPI disclosure | `/docs` e `/openapi.json` pubblici nel runtime. | `audit/FASE_6_sicurezza.md:31`. | S | 6 |
| SEC-07 | 🟠 ALTO | Trasporto/rete | Backend e frontend esposti HTTP su `0.0.0.0`, TLS non verificato. | `audit/FASE_6_sicurezza.md:32`. | M | 6 |
| SEC-08 | 🟠 ALTO | Dipendenze frontend | `npm audit --omit=dev` segnala 12 vulnerabilita, inclusa 1 critica. | `audit/FASE_6_sicurezza.md:33`; `audit/FASE_6_sicurezza.md:74-92`. | M | 6 |
| SEC-09 | 🟠 ALTO | Backup admin | Restore backup costruisce path da input senza normalizzazione/allowlist. | `audit/FASE_6_sicurezza.md:34`. | S/M | 6 |
| SEC-10 | 🟠 ALTO | Docker config | Backend e worker montano `./backend:/app`, sovrascrivendo immagine. | `audit/FASE_6_sicurezza.md:35`. | M | 6 |
| SEC-11 | 🟡 MEDIO | Rate limiting | Rate limiting middleware in memoria per processo. | `audit/FASE_6_sicurezza.md:36`. | M | 6 |
| SEC-12 | 🟡 MEDIO | Security headers | Frontend reale non mostra X-Frame/CSP/HSTS. | `audit/FASE_6_sicurezza.md:37`. | S/M | 6 |
| SEC-13 | 🟡 MEDIO | Server fingerprinting | Backend espone `server: uvicorn`; middleware alternativo non usato. | `audit/FASE_6_sicurezza.md:38`. | S | 6 |
| SEC-14 | 🟡 MEDIO | Upload SVG | Logo SVG accettati senza sanitizzazione contenuto attivo. | `audit/FASE_6_sicurezza.md:39`. | S/M | 6 |
| SEC-15 | 🟡 MEDIO | Log PII | Alcuni log includono dati personali, email, filename/path allegati. | `audit/FASE_6_sicurezza.md:40`. | M | 6 |
| SEC-16 | 🟡 MEDIO | Error handling | Diversi handler restituiscono `detail=str(e)` su errori interni. | `audit/FASE_6_sicurezza.md:41`. | S/M | 6 |
| SEC-17 | 🟢 BASSO | Middleware | Due security middleware; quello con scanning/Server unknown non risulta integrato. | `audit/FASE_6_sicurezza.md:42`. | S | 6 |
| GDPR-01 | 🔴 CRITICO | SaaS/multi-tenancy | Non esiste isolamento tenant. | `audit/FASE_7_gdpr.md:236`; contesto `audit/FASE_7_gdpr.md:210-215`. | L/XL | 7 |
| GDPR-02 | 🔴 CRITICO | Art. 32/access control | Dati personali core accessibili/modificabili da qualunque utente autenticato. | `audit/FASE_7_gdpr.md:237`; `audit/FASE_6_sicurezza.md:28`. | M/L | 7 |
| GDPR-03 | 🔴 CRITICO | Art. 17 | Cancellazione/anonymize incompleta; file, email, agent payload, log e backup restano fuori. | `audit/FASE_7_gdpr.md:238`; conclusione `audit/FASE_7_gdpr.md:143`. | L | 7 |
| GDPR-04 | 🔴 CRITICO | Art. 32/segreti | Backup cifrati, ma chiave backup e segreti sono in `.env`/backup workspace. | `audit/FASE_7_gdpr.md:239`; `audit/FASE_7_gdpr.md:165`. | M | 7 |
| GDPR-05 | 🔴 CRITICO | Audit trail/breach | Non si ricostruisce in modo completo chi ha visto/modificato cosa e quando. | `audit/FASE_7_gdpr.md:240`; conclusione `audit/FASE_7_gdpr.md:184`. | L | 7 |
| GDPR-06 | 🟠 ALTO | Art. 20 | Export portabilita incompleto. | `audit/FASE_7_gdpr.md:241`. | M | 7 |
| GDPR-07 | 🟠 ALTO | Retention | Retention automatica solo parziale; molte categorie dati senza retention. | `audit/FASE_7_gdpr.md:242`. | M/L | 7 |
| GDPR-08 | 🟠 ALTO | Cifratura upload/DB | Cifratura at rest DB/upload non dimostrata; file su volume Docker. | `audit/FASE_7_gdpr.md:243`; `audit/FASE_7_gdpr.md:164-166`. | M/L | 7 |
| GDPR-09 | 🟠 ALTO | AI/sub-responsabili | LLM/email trattano contenuti personali con pseudonimizzazione incompleta e side effect. | `audit/FASE_7_gdpr.md:244`; `audit/FASE_5_agenti_ai.md:111-115`. | M/L | 7 |
| GDPR-10 | 🟠 ALTO | Minimizzazione | Campi social, profiling, note libere e payload raccolgono piu dati del necessario verificato. | `audit/FASE_7_gdpr.md:245`; valutazione `audit/FASE_7_gdpr.md:108`. | M | 7 |
| GDPR-11 | 🟡 MEDIO | Art. 17/FK | FK `CASCADE` possono cancellare storico operativo con hard delete non controllati. | `audit/FASE_7_gdpr.md:246`; `audit/FASE_4_architettura.md:157-173`. | M | 7 |
| GDPR-12 | 🟡 MEDIO | Consensi | Tabella consensi e booleani agenti su collaborator non sono semanticamente unificati. | `audit/FASE_7_gdpr.md:247`. | M | 7 |
| GDPR-13 | 🟡 MEDIO | Backup/DR | Backup schedulati, ma restore test/access control/retention legale non verificati. | `audit/FASE_7_gdpr.md:248`; `audit/FASE_8_saas.md:238`. | M | 7 |
| SAAS-01 | 🔴 CRITICO | Multi-tenancy | Shared SaaS impossibile: nessun tenant isolation DB/app. | `audit/FASE_8_saas.md:232`; `audit/FASE_8_saas.md:21-25`. | L/XL | 8 |
| SAAS-02 | 🔴 CRITICO | Access control | RBAC e tenant scope assenti sui router core. | `audit/FASE_8_saas.md:233`. | M/L | 8 |
| SAAS-03 | 🔴 CRITICO | Segreti/config | Segreti e chiavi in workspace bloccano onboarding cliente. | `audit/FASE_8_saas.md:234`. | M | 8 |
| SAAS-04 | 🟠 ALTO | Config/deploy | Build e runtime non deterministici: requirements, Dockerfile, bind mount, compose prod. | `audit/FASE_8_saas.md:235`; `audit/FASE_8_saas.md:66-85`. | M | 8 |
| SAAS-05 | 🟠 ALTO | Observability | `/metrics` non esiste nel runtime; Prometheus punta a 404; stack monitoring non attivo. | `audit/FASE_8_saas.md:236`. | M | 8 |
| SAAS-06 | 🟠 ALTO | Alerting/SRE | Alerting esterno assente; performance monitor in memoria, Alertmanager/Grafana SMTP commentati. | `audit/FASE_8_saas.md:237`; `audit/FASE_8_saas.md:147`. | M | 8 |
| SAAS-07 | 🟠 ALTO | Backup/DR | Backup esiste, ma DR/restore testato non verificabile. | `audit/FASE_8_saas.md:238`; `audit/FASE_8_saas.md:176`. | M | 8 |
| SAAS-08 | 🟠 ALTO | Deployment | Zero-downtime non dimostrato: backend unico, migration al startup, nessun LB/rolling. | `audit/FASE_8_saas.md:239`; `audit/FASE_8_saas.md:197-201`. | M/L | 8 |
| SAAS-09 | 🟠 ALTO | App runtime | Doppia FastAPI e coverage su mini-app creano rischio release/test su componente sbagliato. | `audit/FASE_8_saas.md:240`; `audit/FASE_3_qualita.md:128-144`. | M | 8 |
| SAAS-10 | 🟠 ALTO | Scalabilita | 2 worker, PDF/report sincroni e N+1 non reggono 100 utenti o molti tenant. | `audit/FASE_8_saas.md:241`; `audit/FASE_8_saas.md:211-224`. | L | 8 |
| SAAS-11 | 🟠 ALTO | AI SaaS | Agenti senza tenant scope, cost control e quote. | `audit/FASE_8_saas.md:242`. | M/L | 8 |
| SAAS-12 | 🟡 MEDIO | Config hardcoded | Link locali, magic link IP LAN, email default locale e CORS manuale. | `audit/FASE_8_saas.md:243`; `audit/FASE_8_saas.md:71-75`. | S/M | 8 |
| SAAS-13 | 🟡 MEDIO | Health | `/health` superficiale, non verifica DB/Redis. | `audit/FASE_8_saas.md:244`. | S | 8 |

## 3. Conteggi finali

| Severita | Conteggio |
|---|---:|
| 🔴 CRITICO | 15 |
| 🟠 ALTO | 38 |
| 🟡 MEDIO | 40 |
| 🟢 BASSO | 7 |
| Totale | 100 |

### Test e coverage

| Voce | Risultato | Prova |
|---|---:|---|
| Test backend configurati | 115 raccolti | `audit/FASE_3_qualita.md:31`; `audit/FASE_3_pytest.txt`. |
| Esito pytest | 115 passed, 2 warnings, 194.43s | `audit/FASE_3_qualita.md:32`; `audit/FASE_3_qualita.md:300`. |
| Coverage dichiarata | 78,75% su `backend/app` | `audit/FASE_3_qualita.md:33`; `audit/FASE_3_qualita.md:301`. |
| Coverage reale runtime commerciale | NON VERIFICABILE: coverage non misura correttamente `backend/main.py`, router runtime, `crud.py`, `models.py`, `services`, agenti e file upload. | `audit/FASE_3_qualita.md:73-88`; `audit/FASE_3_qualita.md:308`. |

### Codice morto stimato

| Categoria | Righe | Prova |
|---|---:|---|
| 5 componenti frontend orfani + file backup + script reset + `backend/app/main.py` | 2.862 | Comando `wc -l frontend/src/components/AgenzieManager.js ... docker-compose.yml.backup` -> `2862`; componenti orfani `audit/FASE_3_qualita.md:237-256`. |
| Mini-app Python `backend/app` non runtime corrente | 1.420 | Comando `wc -l backend/app/*.py backend/app/api/*.py ...` -> `1420`; doppia app `audit/FASE_2_funzionale.md:86`; `audit/FASE_3_qualita.md:128-144`. |
| Stima finale prudente | almeno 2.862 righe, fino a circa 3.750 se si considera tutto `backend/app` come non runtime commerciale | Basata sui due comandi sopra; NON VERIFICABILE come valore esatto senza decisione product/owner su cosa reintegrare. |

### Vulnerabilita dipendenze

| Ecosistema | Esito | Prova |
|---|---|---|
| npm/frontend | 12 vulnerabilita: 1 critica, 2 alte, 8 moderate, 1 low | `audit/FASE_6_sicurezza.md:19`; `audit/FASE_6_sicurezza.md:33`; `audit/FASE_6_sicurezza.md:74-92`. |
| Python/backend | NON VERIFICABILE con audit automatico: `pip-audit` e `safety` assenti su host/container, non installati per vincolo read-only. | `audit/FASE_6_sicurezza.md:92`; `audit/FASE_6_sicurezza.md:110`. |

## 4. Roadmap di remediation

### Ondata 1 - Sicurezza minima per uso interno con dati reali

Obiettivo: permettere un uso interno controllato senza esporre dati personali e credenziali. Senza questa ondata, l'uso con dati reali resta non raccomandato.

| Finding inclusi | Intervento | Effort |
|---|---|---:|
| F1-001, SEC-01, GDPR-04, SAAS-03 | Rimuovere `.env*` e backup dal workspace/repo condiviso, ruotare DB/Redis/JWT/email/WhatsApp/AI/backup key, introdurre secret manager. | M |
| F3-001, SEC-02 | Eliminare o neutralizzare `reset_password.py`, ruotare credenziali admin se usato. | S |
| SEC-03, GDPR-02, SAAS-02 | Applicare RBAC deny-by-default sui router core con permessi read/write/delete. | M/L |
| F3-003, SEC-04, SEC-15 | Redigere token/header/PII dai log, rivedere log storici e retention. | S/M |
| SEC-05 | Spostare refresh token fuori da `localStorage`, introdurre rotazione e revoca. | M |
| SEC-07, SEC-12 | Mettere accesso utente dietro HTTPS e header di sicurezza effettivi sul frontend. | M |
| SEC-08 | Aggiornare dipendenze npm high/critical e bloccare CI su high/critical. | M |
| AI-01, AI-02, AI-03 | Disabilitare auto-mutazione/auto-send/auto-validazione LLM: output agenti solo draft/manual review. | M |
| F2-001, F2-003, F2-004 | Correggere listini `500`, fetch senza Bearer e incoerenza portale allievi. | M |

Effort totale stimato Ondata 1: **M/L**, circa 3-6 settimane uomo se svolta con test regressione.
Dipendenze: segreti e logging prima di test con dati reali; RBAC prima di estendere utenti interni; AI in manual review prima di inbox/documenti reali.

### Ondata 2 - SaaS-ready

Obiettivo: arrivare a un pilota vendibile a terzi, preferibilmente con deployment/DB separato per cliente prima dello shared SaaS.

| Finding inclusi | Intervento | Effort |
|---|---|---:|
| GDPR-01, SAAS-01 | Scegliere tenancy model. Raccomandazione Fase 8: DB-per-tenant o deployment separato come ponte, RLS shared solo dopo hardening. | L/XL |
| GDPR-03, GDPR-06, GDPR-07, GDPR-11, GDPR-12 | Implementare DSAR completo: cancellazione, export, retention, consensi e legal hold per tutte le categorie dati. | L |
| GDPR-05 | Audit trail centralizzato per read/write/delete/export/download, con tenant scope e retention. | L |
| GDPR-08, GDPR-13, SAAS-07 | Cifratura DB/upload o storage cifrato, backup per tenant, restore drill, RPO/RTO. | M/L |
| SAAS-04, F1-005, F1-009, SEC-10 | Build immutabile: un solo requirements/lock, Dockerfile prod unico, niente bind mount codice. | M |
| SAAS-05, SAAS-06, SAAS-13, F2-006 | Attivare `/metrics`, Prometheus/Grafana/Alertmanager, readiness DB/Redis e alerting. | M |
| SAAS-08 | Introdurre deploy con LB/rolling o blue-green e migration controllate fuori startup. | M/L |
| SAAS-11, AI-04, AI-05 | Policy agenti per tenant: quote, cost cap, subprocessor, DPA, opt-out LLM esterno. | M/L |
| SEC-06 | Proteggere o disabilitare docs/OpenAPI in produzione SaaS. | S |

Effort totale stimato Ondata 2: **L/XL**, circa 2-4 mesi per un pilota SaaS separato per tenant; piu' lungo per shared SaaS maturo.
Dipendenze: RBAC e audit trail devono precedere multi-tenancy condivisa; Alembic drift deve essere chiuso prima di migration multi-tenant; backup/restore per tenant deve precedere DPA art. 28.

### Ondata 3 - Qualita e scalabilita

Obiettivo: ridurre debito tecnico, migliorare mantenibilita e reggere carichi superiori.

| Finding inclusi | Intervento | Effort |
|---|---|---:|
| F3-004, F3-008, F4-004 | Estrarre service layer/use case, repository/query object, ridurre `crud.py` e router monolitici. | L |
| F4-001, F4-002 | Transazioni per use case e vincoli/lock DB per overlap temporali. | M/L |
| F3-005, F2-009, SAAS-09 | Eliminare doppia app FastAPI o separarla come test/demo; riallineare Docker, coverage, docs. | M |
| F3-002, F3-011, F3-012 | Coverage sul runtime reale, CI con pytest/ruff/mypy/eslint/npm audit. | M |
| F2-002, F2-005, F2-010, F2-011, F3-013 | Contract test OpenAPI/frontend, rimozione o reintegrazione componenti/API orfani. | M |
| F4-007, F4-008, SAAS-10 | Eliminare N+1, job queue per PDF/report/upload/agenti, cache documenti generati. | L |
| F4-005, F3-010 | Stato frontend unico, progressiva migrazione TypeScript o PropTypes dove il rischio e' alto. | M/L |
| SEC-11, SEC-13, SEC-14, SEC-16, SEC-17 | Hardening residuo: rate limit Redis, fingerprinting, SVG sanitization, error mapping, middleware unico. | M |
| F1-002, F1-008, F2-007 | Chiudere drift Alembic e rimuovere script migration one-shot. | M/L |

Effort totale stimato Ondata 3: **L/XL**, da pianificare come programma di industrializzazione continuo.
Dipendenze: non iniziare grandi refactor prima di congelare entrypoint runtime e test coverage reale; performance job queue utile solo dopo logging/audit/tenant scope.

## 5. Raccomandazione strategica finale

**Non conviene riscrivere tutto da zero.** La base gestionale ha valore: il dominio e' gia' modellato, ci sono 44 tabelle runtime (`audit/FASE_1_inventario.md:73`), 239 operazioni OpenAPI (`audit/FASE_2_funzionale.md:31`), FK/indici reali (`audit/FASE_4_architettura.md:175-188`), una suite test che passa anche se parziale (`audit/FASE_3_qualita.md:31-33`) e componenti AI/backup/monitoring gia' abbozzati (`audit/FASE_5_agenti_ai.md:126-129`; `audit/FASE_8_saas.md:176`).

**Non conviene nemmeno vendere l'esistente con solo hardening superficiale.** Il salto SaaS richiede decisioni strutturali: tenancy, RBAC, audit trail, DSAR, deploy immutabile e osservabilita (`audit/FASE_7_gdpr.md:252-268`; `audit/FASE_8_saas.md:246-277`). Senza questi elementi, il rischio non e' solo tecnico: e' contrattuale, GDPR e reputazionale.

### Tenere e rafforzare

| Parte | Motivo | Prova |
|---|---|---|
| Stack FastAPI/PostgreSQL | Buona base per gestionale API-first. | Runtime OpenAPI `239` operazioni (`audit/FASE_2_funzionale.md:31`); DB 44 tabelle (`audit/FASE_1_inventario.md:73`). |
| Modello dominio principale | Collaboratori, progetti, presenze, contratti, aziende e agenti sono gia' presenti. | Schema DB completo in `audit/FASE_2_db_schema.sql`; Fase 2 conferma 44 tabelle (`audit/FASE_2_funzionale.md:131`). |
| Indici e FK | Esistono indici e FK utili, anche se da rivedere. | `audit/FASE_4_architettura.md:175-188`; `audit/FASE_4_db_fk.txt`. |
| Test esistenti | Utili come base, ma da riallineare al runtime. | `audit/FASE_3_qualita.md:31-33`; problema coverage `audit/FASE_3_qualita.md:73-88`. |

### Ripensare prima del SaaS

| Parte | Decisione raccomandata | Prova |
|---|---|---|
| Multi-tenancy | Progettare DB-per-tenant/deployment separato come ponte; shared RLS solo dopo RBAC/audit/migration solide. | `audit/FASE_8_saas.md:49-54`; `audit/FASE_8_saas.md:277`. |
| Autorizzazione | Passare da autenticazione globale a RBAC/tenant scope server-side deny-by-default. | `audit/FASE_6_sicurezza.md:28`; `audit/FASE_7_gdpr.md:237`. |
| GDPR/data lifecycle | Implementare DSAR completo e audit trail prima di firmare DPA. | `audit/FASE_7_gdpr.md:219-230`; `audit/FASE_7_gdpr.md:236-248`. |
| Runtime/deploy | Eliminare doppia app, bind mount codice e drift Alembic; immutabilita build. | `audit/FASE_3_qualita.md:128-144`; `audit/FASE_6_sicurezza.md:35`; `audit/FASE_1_inventario.md:145`. |
| AI in produzione | Rendere agenti assistivi, non autonomi, finche' non esistono policy tenant/costi/review. | `audit/FASE_5_agenti_ai.md:111-115`; `audit/FASE_8_saas.md:242`. |
| Service layer | Estrarre use case/transazioni da router e `crud.py`. | `audit/FASE_4_architettura.md:35-94`; `audit/FASE_3_qualita.md:104-126`. |

### Decisione consigliata

1. **Fermare qualsiasi vendita SaaS immediata.** Prova: assenza multi-tenancy e readiness `0 tenant production` (`audit/FASE_8_saas.md:21-25`; `audit/FASE_8_saas.md:221`).
2. **Consentire uso interno solo dopo Ondata 1.** Prova: segreti, RBAC, logging token, AI side effect e GDPR cancellazione sono critici (`audit/FASE_6_sicurezza.md:26-29`; `audit/FASE_5_agenti_ai.md:111-115`; `audit/FASE_7_gdpr.md:236-240`).
3. **Preparare un pilota commerciale solo come deployment separato per cliente, non shared SaaS.** Prova: Fase 8 raccomanda non tentare subito shared SaaS e usare DB-per-tenant/deployment separato come ponte (`audit/FASE_8_saas.md:49-54`; `audit/FASE_8_saas.md:277`).
4. **Rifattorizzare parti mirate, non riscrivere tutto.** Prova: fondamenta FastAPI/PostgreSQL/indici/test esistono (`audit/FASE_4_architettura.md:231`; `audit/FASE_8_saas.md:275`), ma service layer, deploy, RBAC, tenancy e GDPR vanno ripensati strutturalmente (`audit/FASE_4_architettura.md:81-94`; `audit/FASE_7_gdpr.md:252-268`).
