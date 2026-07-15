# Finding nuovi emersi durante remediation

## 2026-07-05 | NEW-001 | Backup encryption key non propagata ai container

- Area: segreti / backup runtime
- Severita stimata: alta
- Emerso durante: Ondata 1, punto 1.1 segreti/credenziali
- Descrizione: `BACKUP_ENCRYPTION_KEY` era presente in `.env` e usata da `backend/backup_manager.py`, ma `docker-compose.yml` non la passava esplicitamente ai container backend/backup scheduler.
- Impatto: backup manuali/schedulati potevano fallire o non usare la chiave runtime attesa dopo rotazione.
- Stato: corretto nello stesso intervento SEC-01/GDPR-04 perche necessario a rendere effettiva la rotazione della chiave backup.

## 2026-07-05 | NEW-002 | Volume backup non scrivibile dopo recreate container

- Area: backup runtime / continuita operativa
- Severita stimata: alta
- Emerso durante: Ondata 1, punto 4 RBAC enforcement
- Descrizione: un backup di emergency shutdown falliva con `Permission denied` su `/app/backups/...`; il volume era `0755` con owner `999:1000` mentre l'app gira come `1000:999`.
- Impatto: backup manuali o schedulati potevano fallire in modo silenzioso dopo recreate dei container.
- Cause correlate: home GPG runtime non inizializzata per `appuser`; immagine `backup_scheduler` non ricreata con `gpg` disponibile.
- Fix applicato: owner live volume corretto a `1000:999`, permessi `0775`; cifratura/decifratura backup usa una GNUPGHOME temporanea sicura; ricreate immagini/container backend e backup scheduler.
- Verifica: backup manuale e backup scheduler creati come `.sql.zip.gpg` e verificati con `verify_backup_integrity(...) == True`.
- Stato: corretto nello stesso intervento prima dell'enforcement RBAC reale.


## 2026-07-05 | NEW-003 | Catena Alembic greenfield non completa

- Area: database / deploy governance
- Severita stimata: alta
- Emerso durante: Ondata 1, punto 6 allineamento schema/Alembic
- Descrizione: la catena Alembic da DB vuoto arriva a head ma non produce uno schema completo rispetto al runtime storico; alcune colonne storicamente aggiunte fuori migration, ad esempio `projects.avviso`, richiedono migration difensive o baseline.
- Impatto: un deploy greenfield o restore strutturale da sole migration puo' risultare incompleto anche se il DB live e' allineato e `alembic check` e' pulito.
- Stato: non corretto in Ondata 1; da pianificare in Ondata 2 con baseline migration o consolidamento controllato della catena.

## 2026-07-05 | NEW-004 | Residui npm moderate/low richiedono uscita da react-scripts

- Area: dipendenze frontend / toolchain
- Severita stimata: media
- Emerso durante: Ondata 1, punto 7 dipendenze
- Descrizione: dopo il fix SEC-08, `npm audit` reale segnala ancora 2 moderate e 9 low, tutte nella catena dev/tooling `react-scripts` -> Jest/jsdom/webpack-dev-server/http-proxy-agent/@tootallnate/once.
- Stato audit: `critical=0`, `high=0`, `moderate=2`, `low=9`.
- Fixability: non fixabile in modo minimale senza major/breaking upgrade o migrazione toolchain (es. uscita da CRA/react-scripts verso stack mantenuto). `npm audit fix` propone una risoluzione major/non sicura (`react-scripts` 0.0.0) e quindi non e' stata applicata in Ondata 1.
- Impatto: residuo principalmente dev-server/test tooling; la build production e' riuscita. Resta debito da pianificare in Ondata 2.

## 2026-07-15 | NEW-005 | Endpoint apply-fix fittizio: marcava "implemented" senza applicare nulla

- Area: piattaforma agenti / integrita' del flusso di revisione
- Severita stimata: alta
- Emerso durante: ONDATA AGENTI, punto A1 (task A1.4)
- Descrizione: `POST /api/v1/agents/suggestions/{id}/apply-fix` non applicava alcuna modifica: creava una `AgentReviewAction` con `result_success=True` e marcava la suggestion "implemented" limitandosi a fare eco del payload. L'operatore riceveva conferma di un'applicazione mai avvenuta.
- Impatto: falso senso di completamento; dati proposti dagli agenti mai realmente applicati; audit trail fuorviante (`auto_fix_applied=True` su azione inesistente).
- Stato: corretto in AGENT-04 — `services/agent_apply_service.py` applica davvero il diff con whitelist campi per entity_type, ricontrollo dei valori attuali (skip campi stantii) e `AuditLog` per campo; payload non strutturati vengono rifiutati con 400 invece di essere "confermati".

## 2026-07-15 | NEW-006 | data_retention_cleanup: anonimizzazione e invio email automatici fuori dal flusso agenti

- Area: piattaforma agenti / side effect non revisionati
- Severita stimata: alta
- Emerso durante: ONDATA AGENTI, censimento trigger (A1.1)
- Descrizione: il cron ARQ `data_retention_cleanup` (pre-esistente, untracked in `arq_worker.py`) anonimizza collaboratori e invia una email di report automaticamente ogni domenica alle 03:00, senza AgentRun/AgentSuggestion ne' revisione umana.
- Impatto: modifica irreversibile di dati personali e invio email fuori dal flusso canonico trigger -> proposta -> approvazione.
- Mitigazione: in AGENT-01 il job e' stato messo dietro kill switch globale (`agents_enabled()`).
- Stato: mitigato, non conforme alla spec; conversione a flusso proposta/approvazione da pianificare (A3/spec agenti).

## 2026-07-15 | NEW-007 | /email-inbox/status legge stato in-process: dato stantio cross-process

- Area: piattaforma agenti / osservabilita' inbox IMAP
- Severita stimata: media
- Emerso durante: ONDATA AGENTI, analisi A2.3
- Descrizione: `GET /api/v1/email-inbox/status` legge `_WORKER_STATUS`, un dict in-process di `services/email_inbox_worker.py`. Il polling reale gira nel processo worker ARQ: il backend API risponde con uno stato che non viene mai aggiornato (sempre "mai eseguito"/vuoto).
- Impatto: dashboard e operatori vedono uno stato inbox non veritiero; errori IMAP (es. credenziali scadute) invisibili dal backend.
- Stato: aperto; fix pianificato in A2.3 con store condiviso (Redis con fallback in-memory) e endpoint di test IMAP admin.
