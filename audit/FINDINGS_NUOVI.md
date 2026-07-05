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
