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

