# 📖 RUNBOOK PRODUZIONE - Gestionale Pythonpro

**Versione:** 3.0.0
**Data:** 2025-10-09
**Ambiente:** Windows 11 + Docker Desktop + WSL2

---

## 🎯 Scopo

Questo documento fornisce procedure operative per deployment, manutenzione e troubleshooting del sistema in produzione.

---

## 📋 Pre-requisiti Produzione

- Windows Server 2019+ o Windows 10/11 Pro
- Docker Desktop 4.20+ con WSL2
- Minimo 16GB RAM, 50GB disco SSD
- Backup strategy configurata
- Monitoring esterno (opzionale: Prometheus, Grafana)

---

## 🚀 Deployment Produzione

### 1. Preparazione Iniziale

```powershell
# Clone o trasferimento progetto
cd C:\
git clone <repo> pythonpro  # oppure copia manuale
cd C:\pythonpro

# Verifica file essenziali
ls docker-compose.yml, docker-compose.prod.yml, .env.production.template
```

### 2. Configurazione Environment

```powershell
# Copia template
cp .env.production.template .env

# Genera password sicure
openssl rand -hex 32  # JWT_SECRET_KEY
openssl rand -base64 24  # DB_PASSWORD
openssl rand -base64 24  # REDIS_PASSWORD

# Modifica .env con editor sicuro
notepad .env
```

**Variabili CRITICHE produzione:**
```ini
ENVIRONMENT=production
DEBUG=False
JWT_SECRET_KEY=<generato-openssl>
DB_PASSWORD=<strong-password>
REDIS_PASSWORD=<strong-password>
BACKEND_CORS_ORIGINS=https://tuodominio.com
```

### 3. Build Immagini

```powershell
# Build senza cache
docker compose build --no-cache

# Verifica immagini
docker images | Select-String "pythonpro"
```

### 4. Deploy Stack

```powershell
# Avvio produzione
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Monitoraggio startup
docker compose logs -f --tail=50
```

### 5. Verifica Health

```powershell
# Attendi 60s per healthcheck completo
Start-Sleep -Seconds 60

# Verifica tutti i container healthy
docker compose ps

# Test endpoint
curl http://localhost:8001/health
curl http://localhost:3001/

# Smoke test
.\scripts\smoke_test.ps1
```

**Output atteso:**
```
✅ TUTTI I TEST PASSATI!
pythonpro_db               healthy
pythonpro_redis            healthy
pythonpro_backend          healthy
pythonpro_frontend         healthy
```

---

## 🔄 Operazioni Routine

### Update Applicazione

```powershell
# 1. Backup database
docker compose exec -T backup_scheduler python run_backup.py create --type pre_update

# 2. Pull nuova versione
git pull origin main

# 3. Rebuild immagini
docker compose build --no-cache

# 4. Rolling update (minimizza downtime)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps --build backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps --build frontend

# 5. Verifica
.\scripts\smoke_test.ps1
```

### Restart Servizi

```powershell
# Restart singolo servizio
docker compose restart backend

# Restart completo
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart

# Hard restart (rimuove container)
docker compose down
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## 💾 Backup e Restore

### Backup Database

```powershell
# Backup manuale
docker compose exec -T backup_scheduler python run_backup.py create --type manual

# Elenco backup
docker compose exec -T backup_scheduler python run_backup.py list
```

**Scheduler automatico**
- Servizio: `backup_scheduler`
- Directory: `/app/backups`
- Formato file: `gestionale_backup_<tipo>_<timestamp>.sql.zip`
- Metadata: file `.json` associato

**Variabili configurabili**
```ini
BACKUP_RETENTION_COUNT=30
BACKUP_DAILY_TIME=02:00
BACKUP_WEEKLY_TIME=03:00
BACKUP_MONTHLY_INTERVAL_DAYS=30
```

### Restore Database

```powershell
# 1. Stop backend
docker compose stop backend

# 2. Estrai il dump SQL dal file ZIP in una cartella temporanea
# 3. Restore via psql
Get-Content .\restore\gestionale_backup_manual_YYYYMMDD_HHMMSS.sql | docker compose exec -T db psql -U admin gestionale

# 3. Restart backend
docker compose start backend

# 4. Verifica
.\scripts\smoke_test.ps1
```

Se preferisci il percorso applicativo, il repository include anche l'endpoint admin di restore `/api/v1/admin/restore/{backup_filename}`.

### Backup Volumi

```powershell
# Backup uploads
docker run --rm -v gestionale_backend_uploads_prod:/data -v C:\backups:/backup alpine tar czf /backup/uploads_$(date +%Y%m%d).tar.gz /data

# Restore uploads
docker run --rm -v gestionale_backend_uploads_prod:/data -v C:\backups:/backup alpine tar xzf /backup/uploads_YYYYMMDD.tar.gz -C /
```

---

## 📊 Monitoring

### Health Check

```powershell
# Status container
docker compose ps

# Health endpoint
curl http://localhost:8001/health | ConvertFrom-Json

# Metriche sistema
docker stats --no-stream

# Disk usage
docker system df
```

### Log Management

```powershell
# Logs real-time
docker compose logs -f --tail=100

# Logs singolo servizio
docker compose logs backend -f --tail=50 | Select-String "ERROR"

# Export logs
docker compose logs --since 24h > logs_$(Get-Date -Format yyyyMMdd).txt

# Log rotation automatica
# Docker gestisce automaticamente con max-size e max-file in daemon.json
```

### Alerting Proattivo

**Setup monitoraggio esterno (opzionale):**
1. Prometheus + Grafana per metriche
2. ELK Stack per log aggregation
3. Uptime Robot per availability check

---

## 🔧 Troubleshooting Produzione

### Backend Non Risponde

```powershell
# 1. Verifica container
docker compose ps backend
docker compose logs backend --tail=100

# 2. Verifica health container
docker inspect pythonpro_backend --format='{{.State.Health.Status}}'

# 3. Restart
docker compose restart backend

# 4. Se persiste, rebuilda
docker compose stop backend
docker compose build backend --no-cache
docker compose up -d backend
```

### Database Connection Issues

```powershell
# 1. Verifica DB container
docker compose ps db
docker compose logs db --tail=50

# 2. Test connessione da backend
docker compose exec backend nc -zv db 5432

# 3. Verifica credentials
docker compose exec db psql -U admin -d gestionale_prod -c "SELECT version();"

# 4. Restart DB (ATTENZIONE: breve downtime)
docker compose restart db
```

### Out of Memory

```powershell
# Verifica usage
docker stats --no-stream

# Aumenta limits in docker-compose.prod.yml
# Modifica:
#   resources:
#     limits:
#       memory: 4G  # aumenta da 2G

# Applica
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Disk Full

```powershell
# Verifica spazio
docker system df

# Cleanup logs vecchi
docker system prune -a

# Cleanup volumi inutilizzati (ATTENZIONE!)
docker volume prune
```

---

## 🔐 Sicurezza Produzione

### Password Rotation

```powershell
# 1. Genera nuova password
$newPassword = openssl rand -base64 24

# 2. Update .env
notepad .env  # Modifica DB_PASSWORD

# 3. Update database
docker compose exec db psql -U admin -d gestionale_prod -c "ALTER USER admin WITH PASSWORD '$newPassword';"

# 4. Restart backend
docker compose restart backend
```

### SSL/TLS Setup

Per HTTPS in produzione, usa reverse proxy esterno (es. Nginx, Traefik, Caddy) davanti a Docker.

**Esempio Nginx esterno:**
```nginx
server {
    listen 443 ssl;
    server_name tuodominio.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 📈 Scaling

### Horizontal Scaling Backend

Modifica `docker-compose.prod.yml`:
```yaml
backend:
  deploy:
    replicas: 3  # Aumenta worker
```

Applica:
```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --scale backend=3
```

### Load Balancer

Aggiungi Nginx load balancer davanti a backend replicas.

---

## 📞 Contatti Emergenza

**Team Responsabile:**
- DevOps: devops@team.local
- Database: dba@team.local
- On-call: oncall@team.local

**Escalation:**
1. Verifica health check
2. Consulta questo runbook
3. Check logs: `docker compose logs -f`
4. Se critico: contatta on-call

---

## ✅ Checklist Go-Live

Prima di portare in produzione:

- [ ] `.env` con password sicure generate
- [ ] Backup strategy configurata e testata
- [ ] Monitoring esterno attivo
- [ ] Healthcheck endpoint funzionante
- [ ] Smoke test passati
- [ ] SSL/TLS configurato (se esposto pubblicamente)
- [ ] Firewall configurato
- [ ] Log rotation attiva
- [ ] Documentazione aggiornata
- [ ] Runbook condiviso con team
- [ ] Piano di rollback definito

---

**🎯 Status:** Documento PRODUCTION READY
**Owner:** DevOps Team
**Review:** Trimestrale
