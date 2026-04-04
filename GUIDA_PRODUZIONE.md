# 🚀 GUIDA COMPLETA MESSA IN PRODUZIONE

## ✅ SISTEMA COMPLETAMENTE AUTOMATIZZATO

Il sistema è ora configurato per:
- ✅ Avvio automatico all'accensione del PC
- ✅ Migrazioni database automatiche
- ✅ Monitoring e auto-restart
- ✅ Healthcheck e recovery automatico

---

## 📋 PRIMA CONFIGURAZIONE (una sola volta)

### 1. Installa Docker Desktop
- Scarica da: https://www.docker.com/products/docker-desktop
- Installa e riavvia il PC
- Assicurati che Docker parta automaticamente

### 2. Configura avvio automatico
```batch
Fai clic destro su CONFIGURAZIONE_AVVIO_AUTOMATICO.bat
Seleziona "Esegui come amministratore"
```

Questo configura:
- Avvio automatico Docker Desktop
- Avvio automatico Gestionale al login
- Monitoring automatico ogni 5 minuti

### 3. Prima esecuzione (build completo)
```batch
Doppio clic su AVVIA_GESTIONALE.bat
```

Attendi 2-5 minuti per il build iniziale.

---

## 🔄 USO QUOTIDIANO

### Avvio sistema
**Metodo 1: Automatico**
- Il sistema parte automaticamente al login di Windows
- Non serve fare nulla!

**Metodo 2: Manuale**
```batch
Doppio clic su AVVIO_RAPIDO.bat
```
Tempo: ~60 secondi

### Fermare il sistema
```batch
docker-compose down
```

### Riavviare dopo modifiche codice
```batch
Doppio clic su AVVIA_GESTIONALE.bat
```

---

## 🔧 ACCESSI E CONFIGURAZIONE

### URL Servizi
- **Frontend**: http://localhost:3001
- **Backend API**: http://localhost:8001/docs
- **Database**: localhost:5434

### Credenziali Database
- **Host**: localhost
- **Porta**: 5434
- **Database**: gestionale
- **User**: admin
- **Password**: password123

---

## 🛡️ MIGRAZIONI DATABASE

### Sistema Automatico (Alembic)
Le migrazioni sono completamente automatiche!

- ✅ Si eseguono all'avvio del backend
- ✅ Sincronizzazione schema automatica
- ✅ Rollback disponibile

### Creare nuova migrazione (sviluppo)
```bash
# Entra nel container
docker exec -it pythonpro-backend-1 bash

# Crea migrazione automatica
alembic revision --autogenerate -m "descrizione_modifica"

# Applica migrazione
alembic upgrade head
```

### Verifica stato migrazioni
```bash
docker exec pythonpro-backend-1 alembic current
docker exec pythonpro-backend-1 alembic history
```

---

## 🔍 MONITORING E DIAGNOSTICA

### Verifica stato sistema
```batch
Doppio clic su VERIFICA_SISTEMA.bat
```

Controlla:
- Docker attivo
- Container running
- Backend accessibile
- Frontend accessibile
- Database connesso
- Schema aggiornato

### Visualizza log in tempo reale
```batch
# Tutti i servizi
docker-compose logs -f

# Solo frontend
docker-compose logs -f frontend

# Solo backend
docker-compose logs -f backend

# Solo database
docker-compose logs -f db
```

### Monitoring automatico
Il sistema si auto-monitora ogni 5 minuti:
- Verifica che tutti i servizi siano attivi
- Riavvia automaticamente se necessario
- Esegue migrazioni se mancanti

---

## 🚨 RISOLUZIONE PROBLEMI

### Il sistema non parte
1. Verifica Docker Desktop sia attivo
2. Esegui `VERIFICA_SISTEMA.bat`
3. Guarda i log: `docker-compose logs`
4. Riavvia completo: `AVVIA_GESTIONALE.bat`

### Frontend non carica
1. Attendi 2 minuti (React compila)
2. Verifica backend: http://localhost:8001/health
3. Riavvia frontend: `docker-compose restart frontend`
4. Controlla log: `docker-compose logs frontend`

### Backend errore 500
1. Controlla log: `docker-compose logs backend`
2. Verifica database: `docker ps | findstr db`
3. Verifica migrazioni: `docker exec pythonpro-backend-1 alembic current`
4. Riavvia: `docker-compose restart backend`

### Database non connesso
1. Controlla container: `docker ps | findstr db`
2. Verifica porta: `netstat -ano | findstr :5434`
3. Test connessione: `docker exec pythonpro-db-1 psql -U admin -d gestionale -c "SELECT 1;"`

### Errore "migrazioni mancanti"
```bash
# Entra nel backend
docker exec -it pythonpro-backend-1 bash

# Esegui manualmente
python init_db.py
```

---

## 💾 BACKUP E RIPRISTINO

### Backup database completo
```batch
docker exec pythonpro-db-1 pg_dump -U admin gestionale > backup_%date:~-4,4%%date:~-7,2%%date:~-10,2%.sql
```

### Ripristino database
```batch
docker exec -i pythonpro-db-1 psql -U admin gestionale < backup_20251001.sql
```

### Backup solo dati (no schema)
```batch
docker exec pythonpro-db-1 pg_dump -U admin -a gestionale > dati_backup.sql
```

---

## 🔐 SICUREZZA PRODUZIONE

### ⚠️ IMPORTANTE: Prima della produzione

1. **Cambia password database**
   - Modifica in `docker-compose.yml`: `POSTGRES_PASSWORD`
   - Modifica in `backend/alembic.ini`: URL connessione
   - Modifica in `backend/.env`: `DATABASE_URL`

2. **Configura SECRET_KEY sicura**
   ```bash
   # Genera chiave sicura
   python -c "import secrets; print(secrets.token_urlsafe(32))"

   # Aggiorna in docker-compose.yml
   ```

3. **Configura CORS produzione**
   - Modifica `backend/main.py`: `allow_origins`
   - Usa solo domini specifici, no "*"

4. **SSL/HTTPS**
   - Usa reverse proxy (Nginx/Traefik)
   - Configura certificati Let's Encrypt

5. **Firewall**
   - Chiudi porte esterne (3001, 8000, 5433)
   - Usa solo reverse proxy pubblico

---

## 📊 PERFORMANCE

### Limiti risorse container
Aggiungi in `docker-compose.yml`:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

### Ottimizzazione database
```sql
-- Vacuum periodico
VACUUM ANALYZE;

-- Reindex
REINDEX DATABASE gestionale;
```

---

## 📞 SUPPORTO

### Comandi utili rapidi
```batch
# Stato sistema
docker-compose ps

# Restart singolo servizio
docker-compose restart frontend
docker-compose restart backend

# Rebuild singolo servizio
docker-compose up -d --build backend

# Pulisci tutto e ricrea
docker-compose down -v
docker-compose up -d --build

# Spazio Docker
docker system df
docker system prune -a
```

### File di configurazione importanti
- `docker-compose.yml` - Configurazione servizi
- `backend/alembic/versions/` - Migrazioni database
- `backend/init_db.py` - Inizializzazione automatica
- `backend/entrypoint.sh` - Startup backend

---

## ✅ CHECKLIST PRODUZIONE

- [ ] Docker Desktop installato e avviato
- [ ] Avvio automatico configurato (`CONFIGURAZIONE_AVVIO_AUTOMATICO.bat`)
- [ ] Password database modificata
- [ ] SECRET_KEY aggiornata
- [ ] CORS configurato correttamente
- [ ] SSL/HTTPS abilitato (se pubblico)
- [ ] Firewall configurato
- [ ] Backup automatico pianificato
- [ ] Monitoring attivo
- [ ] Test completo eseguito (`VERIFICA_SISTEMA.bat`)

---

## 🎯 IL SISTEMA È PRONTO!

Dopo aver completato la configurazione iniziale, il sistema:
- ✅ Parte automaticamente all'accensione del PC
- ✅ Si auto-monitora e auto-ripara
- ✅ Gestisce le migrazioni database automaticamente
- ✅ È pronto per la produzione

**Non serve più intervento manuale!**

Per qualsiasi problema, esegui `VERIFICA_SISTEMA.bat` per diagnostica completa.
