# Production Deployment Guide - PythonPro

**Date:** 2025-10-24
**Stack:** FastAPI Backend + React Frontend + Nginx Reverse Proxy
**Deployment:** Docker Compose Production Configuration

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Configuration](#configuration)
5. [Build & Deploy](#build--deploy)
6. [Verification & Testing](#verification--testing)
7. [Troubleshooting](#troubleshooting)
8. [Security Considerations](#security-considerations)
9. [Scaling & Performance](#scaling--performance)
10. [Backup & Maintenance](#backup--maintenance)

---

## 🏗️ Architecture Overview

### Production Stack Components

```
                                    ┌─────────────────┐
                                    │   User Browser  │
                                    └────────┬────────┘
                                             │
                                             ▼
                    ┌────────────────────────────────────────┐
                    │  Nginx (Port 80)                       │
                    │  - Serves static React build           │
                    │  - Reverse proxy /api/v1 → backend     │
                    │  - Security headers, gzip, caching     │
                    └────────┬──────────────────┬────────────┘
                             │                  │
                Static Files │                  │ API Requests
                             │                  │
                    ┌────────▼─────────┐        │
                    │  React Frontend  │        │
                    │  (Static Build)  │        │
                    └──────────────────┘        │
                                                 │
                                                 ▼
                                    ┌────────────────────────┐
                                    │  FastAPI Backend       │
                                    │  - Gunicorn + Uvicorn  │
                                    │  - API at /api/v1      │
                                    │  - Port 8000 (internal)│
                                    └───────────┬────────────┘
                                                │
                                                ▼
                                    ┌────────────────────────┐
                                    │  SQLite Database       │
                                    │  (or PostgreSQL)       │
                                    └────────────────────────┘
```

### Network Flow

1. **User accesses `http://your-host/`**
   - Nginx serves `index.html` and static assets (JS, CSS, images)
   - React app loads in browser

2. **React app makes API call to `/api/v1/projects`**
   - Browser sends: `GET http://your-host/api/v1/projects`
   - Nginx proxies to: `http://backend:8000/api/v1/projects`
   - FastAPI handles request and returns JSON

3. **No CORS issues** because frontend and API share the same origin (same host)

---

## ✅ Prerequisites

### Required Software

- **Docker**: 24.0+ (with Docker Compose v2)
- **Git**: For version control
- **Bash**: For running deployment scripts

### System Requirements

- **Minimum:** 2 CPU cores, 4GB RAM, 10GB disk
- **Recommended:** 4 CPU cores, 8GB RAM, 20GB disk

### Port Requirements

Ensure these ports are available:
- **80** (HTTP) - Frontend Nginx
- Optionally **443** (HTTPS) - If adding TLS

---

## 🚀 Quick Start

### Option 1: Automated Scripts (Recommended)

```bash
# 1. Clone or navigate to the repository
cd /path/to/pythonpro

# 2. Build production images
bash scripts/build-prod.sh

# 3. Start the stack
bash scripts/up-prod.sh

# 4. Access the application
# Open http://localhost in your browser
```

### Option 2: Manual Docker Compose

```bash
# Build images
docker compose -f docker-compose.prod.yml build

# Start services
docker compose -f docker-compose.prod.yml up -d

# View logs
docker compose -f docker-compose.prod.yml logs -f

# Stop services
docker compose -f docker-compose.prod.yml down
```

---

## ⚙️ Configuration

### 1. Frontend Configuration

**File:** `frontend/.env.production`

```env
# API base path (relative, works behind Nginx)
REACT_APP_API_URL=/api/v1

# Build optimizations
GENERATE_SOURCEMAP=false
SKIP_PREFLIGHT_CHECK=true
```

**Key Points:**
- ✅ Uses **relative path** `/api/v1` (not absolute `http://localhost:8001/api/v1`)
- ✅ This ensures the frontend works behind any domain/host
- ✅ Nginx proxies `/api/v1/*` to the backend container

### 2. Backend Configuration

**File:** `docker-compose.prod.yml` (environment section)

```yaml
environment:
  - ENVIRONMENT=production
  - PORT=8000
  - DATABASE_URL=sqlite:///./gestionale_new.db
  - SECRET_KEY=${SECRET_KEY:-change-me-in-production}
  - JWT_SECRET=${JWT_SECRET:-change-me-in-production}
```

**⚠️ Security Critical:**
- **Change `SECRET_KEY` and `JWT_SECRET` before deploying!**
- Use strong, random values (32+ characters)
- Store in environment variables or secrets manager

**Generate secure secrets:**
```bash
# Linux/Mac
openssl rand -hex 32

# Python
python -c "import secrets; print(secrets.token_hex(32))"
```

**Set via environment variables:**
```bash
export SECRET_KEY="your-super-secret-key-here"
export JWT_SECRET="your-jwt-secret-here"
docker compose -f docker-compose.prod.yml up -d
```

### 3. Database Configuration

**Default:** SQLite (file-based, suitable for small-to-medium deployments)

**Upgrade to PostgreSQL (recommended for production):**

1. Uncomment PostgreSQL service in `docker-compose.prod.yml`:

```yaml
postgres:
  image: postgres:16-alpine
  environment:
    - POSTGRES_USER=pythonpro
    - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-changeme}
    - POSTGRES_DB=pythonpro
  volumes:
    - postgres_data:/var/lib/postgresql/data
```

2. Update backend environment:

```yaml
- DATABASE_URL=postgresql://pythonpro:${POSTGRES_PASSWORD}@postgres:5432/pythonpro
```

3. Uncomment volumes section at bottom:

```yaml
volumes:
  postgres_data:
```

### 4. CORS Configuration

**Current Setup:**
```python
# backend/main.py (line ~141)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Production Considerations:**
- ✅ **Behind Nginx**: CORS is not strictly necessary (same origin)
- ✅ **If using subdomain API**: Add your production domain to `allow_origins`

**Example for production domain:**
```python
allow_origins=[
    "https://yourdomain.com",
    "https://www.yourdomain.com",
]
```

---

## 🔨 Build & Deploy

### Step 1: Build Images

```bash
bash scripts/build-prod.sh
```

This will:
- ✅ Build backend Docker image with Gunicorn + Uvicorn
- ✅ Build frontend Docker image (React build + Nginx)
- ⏱️ Takes ~5-10 minutes on first build

**Troubleshooting Build Issues:**

If build fails on frontend:
```bash
# Check Node version in Dockerfile (should be 20-alpine)
# Verify package.json exists in frontend/
# Check if build/ directory is being created
```

If build fails on backend:
```bash
# Verify requirements.txt exists in backend/
# Check Python version in Dockerfile (should be 3.12-slim)
# Ensure all dependencies are in requirements.txt
```

### Step 2: Start Services

```bash
bash scripts/up-prod.sh
```

This will:
- ✅ Start backend container (port 8000 internal)
- ✅ Wait for backend health check to pass
- ✅ Start frontend Nginx container (port 80 exposed)
- ✅ Display service status

### Step 3: Verify Deployment

```bash
# Check service status
docker compose -f docker-compose.prod.yml ps

# Expected output:
# NAME                     STATUS              PORTS
# pythonpro_backend_prod   Up (healthy)        8000/tcp
# pythonpro_frontend_prod  Up (healthy)        0.0.0.0:80->80/tcp
```

---

## ✔️ Verification & Testing

### 1. Health Checks

```bash
# Nginx health endpoint
curl http://localhost/healthz
# Expected: "ok"

# Backend health endpoint (via Nginx proxy)
curl http://localhost/api/v1/../health
# Expected: {"status": "healthy"} or similar
```

### 2. Frontend Access

```bash
# Open in browser
open http://localhost

# Or with curl
curl -I http://localhost
# Expected: HTTP/1.1 200 OK
```

### 3. API Endpoint Test

```bash
# Test projects endpoint
curl http://localhost/api/v1/projects?limit=1

# Test collaborators endpoint
curl http://localhost/api/v1/collaborators?limit=1

# Expected: JSON response with data
```

### 4. Browser DevTools Check

1. Open browser DevTools (F12)
2. Go to **Network** tab
3. Reload page
4. Verify:
   - ✅ Static assets (JS, CSS) return 200 OK
   - ✅ API calls go to `/api/v1/*` and return 200 OK
   - ✅ No 404 errors
   - ✅ No CORS errors in console
   - ✅ No React error #31

### 5. Security Headers Verification

```bash
curl -I http://localhost | grep -E 'X-Frame-Options|X-Content-Type|CSP'

# Expected:
# X-Frame-Options: SAMEORIGIN
# X-Content-Type-Options: nosniff
# Content-Security-Policy: default-src 'self'; ...
```

---

## 🔧 Troubleshooting

### Issue 1: Port 80 Already in Use

**Symptom:** `Error starting userland proxy: listen tcp4 0.0.0.0:80: bind: address already in use`

**Solution:**
```bash
# Find what's using port 80
sudo lsof -i :80

# Option A: Stop the conflicting service
sudo systemctl stop apache2  # or nginx

# Option B: Change the port in docker-compose.prod.yml
ports:
  - "8080:80"  # Access at http://localhost:8080
```

### Issue 2: Backend Container Unhealthy

**Symptom:** Backend container status shows `unhealthy`

**Diagnosis:**
```bash
# Check backend logs
docker compose -f docker-compose.prod.yml logs backend

# Common issues:
# - Database connection failed
# - Missing environment variables
# - Python dependencies missing
```

**Solutions:**
```bash
# If database issue, check DATABASE_URL
# If dependency issue, rebuild:
docker compose -f docker-compose.prod.yml build --no-cache backend
```

### Issue 3: API Returns 404

**Symptom:** Browser shows 404 for `/api/v1/projects`

**Diagnosis:**
```bash
# Test backend directly (inside container)
docker exec pythonpro_backend_prod wget -qO- http://localhost:8000/health

# Test Nginx proxy
curl http://localhost/api/v1/projects
```

**Common Causes:**
- ❌ Nginx config incorrect (`location /api/v1/` mismatch)
- ❌ Backend not serving on `/api/v1` path
- ❌ Backend container not running

**Solution:**
```bash
# Verify Nginx config
docker exec pythonpro_frontend_prod cat /etc/nginx/conf.d/frontend.conf

# Check backend routes
docker exec pythonpro_backend_prod python -c "from main import app; print(app.routes)"
```

### Issue 4: Frontend Shows White Page

**Symptom:** Browser loads but shows blank page

**Diagnosis:**
```bash
# Check browser console for errors
# Common issues:
# - JS bundle failed to load
# - API calls failing
# - React error

# Check Nginx logs
docker compose -f docker-compose.prod.yml logs frontend
```

**Solution:**
```bash
# Verify build/ directory was created
docker exec pythonpro_frontend_prod ls -la /usr/share/nginx/html

# Rebuild frontend
docker compose -f docker-compose.prod.yml build --no-cache frontend
docker compose -f docker-compose.prod.yml up -d frontend
```

### Issue 5: CORS Errors

**Symptom:** Browser console shows CORS policy errors

**Cause:** Frontend making requests to external domain or wrong CORS config

**Solution:**
```bash
# If using Nginx proxy (same origin), CORS shouldn't be an issue
# If you see CORS errors, verify:

# 1. Frontend is using relative URL /api/v1 (not http://localhost:8001/api/v1)
cat frontend/.env.production | grep REACT_APP_API_URL

# 2. Requests are going through Nginx
# Open browser DevTools → Network tab
# Verify requests show: http://localhost/api/v1/... (not localhost:8001)
```

### Issue 6: Database Persistence

**Symptom:** Data lost after container restart

**Solution:**
```bash
# Verify volume mounts in docker-compose.prod.yml
# For SQLite:
volumes:
  - ./backend/gestionale_new.db:/app/gestionale_new.db

# Check if file exists
ls -la backend/gestionale_new.db

# For PostgreSQL, verify named volume:
docker volume ls | grep postgres
```

---

## 🔒 Security Considerations

### 1. Secrets Management

**❌ DO NOT:**
- Commit secrets to Git
- Use default passwords in production
- Store secrets in .env files committed to repo

**✅ DO:**
```bash
# Use environment variables
export SECRET_KEY="$(openssl rand -hex 32)"
export JWT_SECRET="$(openssl rand -hex 32)"
docker compose -f docker-compose.prod.yml up -d

# Or use Docker secrets (for Docker Swarm)
echo "your-secret-key" | docker secret create secret_key -

# Or use cloud provider secrets manager
# AWS Secrets Manager, GCP Secret Manager, Azure Key Vault
```

### 2. TLS/HTTPS Setup

**Option A: Nginx with Let's Encrypt (Certbot)**

1. Install Certbot:
```bash
sudo apt-get install certbot python3-certbot-nginx
```

2. Obtain certificate:
```bash
sudo certbot --nginx -d yourdomain.com
```

3. Certbot auto-updates Nginx config for HTTPS

**Option B: Reverse Proxy (Traefik, Caddy)**

Use Traefik or Caddy in front of Nginx for automatic TLS:

```yaml
# Add to docker-compose.prod.yml
traefik:
  image: traefik:v2.10
  command:
    - "--providers.docker=true"
    - "--entrypoints.web.address=:80"
    - "--entrypoints.websecure.address=:443"
    - "--certificatesresolvers.myresolver.acme.tlschallenge=true"
    - "--certificatesresolvers.myresolver.acme.email=you@example.com"
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
    - ./letsencrypt:/letsencrypt

frontend:
  labels:
    - "traefik.enable=true"
    - "traefik.http.routers.frontend.rule=Host(`yourdomain.com`)"
    - "traefik.http.routers.frontend.entrypoints=websecure"
    - "traefik.http.routers.frontend.tls.certresolver=myresolver"
```

### 3. Network Isolation

```yaml
# Ensure backend is not exposed directly
backend:
  expose:
    - "8000"  # ✅ Internal only
  # ports:    # ❌ Don't expose publicly
  #   - "8000:8000"
```

### 4. Non-Root Users

✅ Both Dockerfiles use non-root users:
- Frontend: `USER nginx`
- Backend: `USER appuser`

### 5. Security Headers (Already Configured)

✅ Nginx adds security headers:
- `X-Frame-Options: SAMEORIGIN`
- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection: 1; mode=block`
- `Content-Security-Policy: ...`

---

## 📈 Scaling & Performance

### Horizontal Scaling

**Option 1: Multiple Backend Workers**

Increase workers in `docker-compose.prod.yml`:
```yaml
backend:
  environment:
    - UVICORN_WORKERS=4  # Increase based on CPU cores
```

Or adjust in `backend/Dockerfile.prod`:
```dockerfile
CMD ["gunicorn", "--workers", "4", ...]
```

**Option 2: Multiple Backend Containers**

```yaml
backend:
  deploy:
    replicas: 3
```

Add load balancer (Nginx upstream or external LB).

### Vertical Scaling

Allocate more resources:
```yaml
backend:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 4G
      reservations:
        cpus: '1'
        memory: 2G
```

### Caching

**Add Redis for caching:**

Uncomment Redis service in `docker-compose.prod.yml` and configure backend to use it.

### Database Optimization

- Use PostgreSQL instead of SQLite for production
- Enable connection pooling
- Add indexes to frequently queried columns

---

## 💾 Backup & Maintenance

### Database Backup

**For SQLite:**
```bash
# Backup
docker exec pythonpro_backend_prod cp /app/gestionale_new.db /app/backup_$(date +%Y%m%d).db
docker cp pythonpro_backend_prod:/app/backup_$(date +%Y%m%d).db ./backups/

# Restore
docker cp ./backups/backup_20251024.db pythonpro_backend_prod:/app/gestionale_new.db
docker compose -f docker-compose.prod.yml restart backend
```

**For PostgreSQL:**
```bash
# Backup
docker exec pythonpro_postgres_prod pg_dump -U pythonpro pythonpro > backup_$(date +%Y%m%d).sql

# Restore
docker exec -i pythonpro_postgres_prod psql -U pythonpro pythonpro < backup_20251024.sql
```

### Log Rotation

Docker handles log rotation by default. Configure in `/etc/docker/daemon.json`:
```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

### Updates & Maintenance

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
bash scripts/build-prod.sh
docker compose -f docker-compose.prod.yml up -d

# Zero-downtime deployment (if using multiple replicas)
docker compose -f docker-compose.prod.yml up -d --no-deps --build backend
```

---

## 📊 Monitoring & Logging

### View Logs

```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f frontend

# Since specific time
docker compose -f docker-compose.prod.yml logs --since 2024-10-24T10:00:00

# Last N lines
docker compose -f docker-compose.prod.yml logs --tail=100 backend
```

### Container Stats

```bash
# Real-time stats
docker stats pythonpro_backend_prod pythonpro_frontend_prod

# One-time snapshot
docker stats --no-stream
```

### Health Monitoring

Set up external monitoring:
- **Uptime monitoring:** UptimeRobot, Pingdom, StatusCake
- **Application monitoring:** New Relic, Datadog, Prometheus + Grafana
- **Log aggregation:** ELK stack, Loki, Papertrail

---

## 🎯 Auto-Detected Configuration

### Frontend Build Tool

**Detected:** Create React App (CRA)
- ✅ Uses `react-scripts build`
- ✅ Output directory: `build/`
- ✅ Configured in `frontend/Dockerfile.prod`

If using Vite instead:
```dockerfile
# Change in Dockerfile.prod:
RUN npm run build
# Output would be dist/ instead of build/
# Update COPY line:
COPY --from=build /app/dist /usr/share/nginx/html
```

### Backend Dependency Management

**Detected:** requirements.txt
- ✅ Uses pip to install dependencies
- ✅ Configured in `backend/Dockerfile.prod`

If using Poetry:
```dockerfile
# Change in Dockerfile.prod:
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-dev
```

### FastAPI App Instance

**Detected:** `main:app` (line 74 in backend/main.py)
- ✅ Configured in Gunicorn command
- ✅ No changes needed

---

## 📝 Summary of Changes

### Files Created

1. ✅ `frontend/.env.production` - Production environment config
2. ✅ `frontend/Dockerfile.prod` - Multi-stage frontend build
3. ✅ `frontend/nginx/frontend.conf` - Nginx reverse proxy config
4. ✅ `frontend/.dockerignore` - Exclude unnecessary files from build
5. ✅ `backend/Dockerfile.prod` - Production backend image
6. ✅ `backend/.dockerignore` - Exclude unnecessary files from build
7. ✅ `docker-compose.prod.yml` - Production orchestration
8. ✅ `scripts/build-prod.sh` - Automated build script
9. ✅ `scripts/up-prod.sh` - Automated startup script
10. ✅ `scripts/down-prod.sh` - Automated shutdown script

### Files Modified

- None (existing dev config left untouched)

---

## 🚦 Deployment Checklist

Before going live:

- [ ] Set strong `SECRET_KEY` and `JWT_SECRET`
- [ ] Review and restrict CORS origins if needed
- [ ] Switch from SQLite to PostgreSQL (recommended)
- [ ] Set up TLS/HTTPS with valid certificate
- [ ] Configure firewall rules (allow 80, 443; block 8000)
- [ ] Set up automated backups
- [ ] Configure log aggregation
- [ ] Set up monitoring and alerts
- [ ] Test health endpoints
- [ ] Perform load testing
- [ ] Document rollback procedure
- [ ] Test disaster recovery

---

## 🆘 Support & Documentation

- **Project Repository:** (Add your Git URL)
- **Issue Tracker:** (Add your issue tracker URL)
- **Documentation:** See this file and `FIX_REPORT_LOCAL.md`
- **FastAPI Docs:** https://fastapi.tiangolo.com
- **React Docs:** https://react.dev
- **Nginx Docs:** https://nginx.org/en/docs
- **Docker Docs:** https://docs.docker.com

---

**Last Updated:** 2025-10-24
**Maintained By:** DevOps Team
**Version:** 1.0.0
