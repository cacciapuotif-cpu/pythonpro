# ============================================================
# 🚀 SCRIPT AVVIO PULITO - Windows/WSL
# ============================================================
# Script PowerShell per avviare stack Docker in modo affidabile
# Gestisce WSL, Docker Desktop, cleanup e startup
#
# UTILIZZO:
#   .\tools\avvio_pulito.ps1
#
# OPZIONI:
#   -Clean: Esegue pulizia completa (wsl --shutdown, restart servizi)
#   -Build: Rebuilda le immagini prima di avviare
#   -Prod: Usa profilo produzione
#
# ESEMPI:
#   .\tools\avvio_pulito.ps1 -Clean
#   .\tools\avvio_pulito.ps1 -Build
#   .\tools\avvio_pulito.ps1 -Clean -Prod
# ============================================================

param(
    [switch]$Clean,
    [switch]$Build,
    [switch]$Prod
)

$ErrorActionPreference = "Continue"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "🚀 AVVIO PULITO - Gestionale Pythonpro" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# === FUNZIONI ===

function Write-Step {
    param([string]$Message)
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')]" -ForegroundColor DarkGray -NoNewline
    Write-Host " $Message" -ForegroundColor Green
}

function Write-Warning-Custom {
    param([string]$Message)
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')]" -ForegroundColor DarkGray -NoNewline
    Write-Host " ⚠️  $Message" -ForegroundColor Yellow
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')]" -ForegroundColor DarkGray -NoNewline
    Write-Host " ❌ $Message" -ForegroundColor Red
}

# === STEP 1: CLEANUP WSL E SERVIZI (se richiesto) ===
if ($Clean) {
    Write-Step "Pulizia WSL e servizi Windows..."

    # Shutdown WSL
    Write-Host "  → Shutdown WSL..." -ForegroundColor Gray
    wsl --shutdown
    Start-Sleep -Seconds 3

    # Restart servizi Docker-related
    Write-Host "  → Restart servizio vmcompute..." -ForegroundColor Gray
    try {
        Restart-Service -Name "vmcompute" -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    } catch {
        Write-Warning-Custom "Impossibile riavviare vmcompute (potrebbe richiedere privilegi admin)"
    }

    Write-Host "  → Restart servizio HNS (Host Network Service)..." -ForegroundColor Gray
    try {
        Restart-Service -Name "hns" -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    } catch {
        Write-Warning-Custom "Impossibile riavviare HNS (potrebbe richiedere privilegi admin)"
    }

    Write-Step "✅ Cleanup completato"
    Write-Host ""
}

# === STEP 2: VERIFICA DOCKER DESKTOP ===
Write-Step "Verifica Docker Desktop..."

$dockerRunning = $false
try {
    docker info | Out-Null
    $dockerRunning = $true
    Write-Host "  ✅ Docker Desktop attivo" -ForegroundColor Green
} catch {
    Write-Warning-Custom "Docker Desktop non risponde"
}

if (-not $dockerRunning) {
    Write-Step "Avvio Docker Desktop..."

    $dockerPath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerPath) {
        Start-Process $dockerPath
        Write-Host "  → Attendi avvio Docker Desktop (max 60s)..." -ForegroundColor Gray

        $timeout = 60
        $elapsed = 0
        while ($elapsed -lt $timeout) {
            Start-Sleep -Seconds 5
            $elapsed += 5
            try {
                docker info | Out-Null
                Write-Step "✅ Docker Desktop avviato"
                $dockerRunning = $true
                break
            } catch {
                Write-Host "  ... ancora in attesa ($elapsed/$timeout s)" -ForegroundColor DarkGray
            }
        }

        if (-not $dockerRunning) {
            Write-Error-Custom "Docker Desktop non si avvia. Avvialo manualmente e riprova."
            exit 1
        }
    } else {
        Write-Error-Custom "Docker Desktop non trovato in: $dockerPath"
        Write-Host "  Installalo da: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host ""

# === STEP 3: NAVIGAZIONE DIRECTORY PROGETTO ===
Write-Step "Navigazione directory progetto..."
$scriptDir = Split-Path -Parent $PSCommandPath
$projectRoot = Split-Path -Parent $scriptDir
Set-Location $projectRoot
Write-Host "  → Directory: $projectRoot" -ForegroundColor Gray
Write-Host ""

# === STEP 4: STOP CONTAINER ESISTENTI ===
Write-Step "Stop container esistenti..."
docker compose down
Write-Host ""

# === STEP 5: BUILD IMMAGINI (se richiesto) ===
if ($Build) {
    Write-Step "Build immagini Docker..."
    docker compose build --no-cache
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "Build fallito"
        exit 1
    }
    Write-Host ""
}

# === STEP 6: AVVIO STACK ===
Write-Step "Avvio stack Docker..."

if ($Prod) {
    Write-Host "  → Modalità: PRODUZIONE" -ForegroundColor Magenta
    docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
} else {
    Write-Host "  → Modalità: SVILUPPO" -ForegroundColor Cyan
    docker compose up -d --build
}

if ($LASTEXITCODE -ne 0) {
    Write-Error-Custom "Avvio stack fallito"
    exit 1
}

Write-Host ""

# === STEP 7: ATTESA HEALTHCHECK ===
Write-Step "Attesa healthcheck container (max 90s)..."

$timeout = 90
$elapsed = 0
$allHealthy = $false

while ($elapsed -lt $timeout) {
    Start-Sleep -Seconds 5
    $elapsed += 5

    $containers = docker compose ps --format json | ConvertFrom-Json
    $total = $containers.Count
    $healthy = ($containers | Where-Object { $_.Health -eq "healthy" }).Count
    $starting = ($containers | Where-Object { $_.Health -eq "starting" -or $_.Health -eq "" }).Count

    Write-Host "  [$elapsed/$timeout s] Healthy: $healthy/$total" -ForegroundColor DarkGray

    if ($healthy -eq $total -and $total -gt 0) {
        $allHealthy = $true
        break
    }
}

Write-Host ""

# === STEP 8: STATUS FINALE ===
Write-Step "Status finale container:"
docker compose ps

Write-Host ""

if ($allHealthy) {
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "✅ TUTTI I CONTAINER SONO HEALTHY!" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
} else {
    Write-Warning-Custom "Alcuni container potrebbero non essere healthy. Verifica i log:"
    Write-Host "  docker compose logs -f" -ForegroundColor Yellow
}

Write-Host ""

# === STEP 9: TEST ENDPOINT ===
Write-Step "Test endpoint API..."
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8001/health" -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "  ✅ Backend API: OK" -ForegroundColor Green
        Write-Host "  Response: $($response.Content)" -ForegroundColor Gray
    }
} catch {
    Write-Warning-Custom "Backend API non risponde ancora. Potrebbe servire più tempo."
}

Write-Host ""

# === STEP 10: URL UTILI ===
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "📌 URL UTILI:" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Frontend:       http://localhost:3001" -ForegroundColor White
Write-Host "  Backend API:    http://localhost:8001" -ForegroundColor White
Write-Host "  API Docs:       http://localhost:8001/docs" -ForegroundColor White
Write-Host "  Health Check:   http://localhost:8001/health" -ForegroundColor White
Write-Host "  Database:       localhost:5434 (user: admin)" -ForegroundColor White
Write-Host "  Redis:          localhost:6381" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# === FINE ===
Write-Step "✅ Avvio completato!"
Write-Host ""
