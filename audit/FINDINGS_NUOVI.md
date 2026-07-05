# Finding nuovi emersi durante remediation

## 2026-07-05 | NEW-001 | Backup encryption key non propagata ai container

- Area: segreti / backup runtime
- Severita stimata: alta
- Emerso durante: Ondata 1, punto 1.1 segreti/credenziali
- Descrizione: `BACKUP_ENCRYPTION_KEY` era presente in `.env` e usata da `backend/backup_manager.py`, ma `docker-compose.yml` non la passava esplicitamente ai container backend/backup scheduler.
- Impatto: backup manuali/schedulati potevano fallire o non usare la chiave runtime attesa dopo rotazione.
- Stato: corretto nello stesso intervento SEC-01/GDPR-04 perche necessario a rendere effettiva la rotazione della chiave backup.
