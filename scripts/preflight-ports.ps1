# ============================================================
# PYTHONPRO - Preflight Port Check (PowerShell)
# ============================================================
# Verifica che tutte le porte richieste siano libere prima
# di avviare lo stack Docker
# ============================================================

Param()
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$envPath = Join-Path $projectRoot ".env"

# Verifica esistenza .env
if (-not (Test-Path $envPath)) {
    Write-Error "❌ File .env non trovato in: $projectRoot"
    exit 1
}

# Leggi variabili d'ambiente
$envVars = @{}
Get-Content $envPath | Where-Object {
    $_ -match '^\s*([^#=]+)\s*=\s*(.+)\s*$'
} | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)\s*=\s*(.+)\s*$') {
        $envVars[$matches[1].Trim()] = $matches[2].Trim()
    }
}

$projectName = $envVars['COMPOSE_PROJECT_NAME']
if (-not $projectName) { $projectName = "pythonpro" }

# Porte da verificare
$ports = @(
    $envVars['FRONTEND_PORT'],
    $envVars['BACKEND_PORT'],
    $envVars['POSTGRES_PORT'],
    $envVars['REDIS_PORT']
) | Where-Object { $_ -and $_ -ne "" }

# Prepara log
$artifactsDir = Join-Path $projectRoot "artifacts"
if (-not (Test-Path $artifactsDir)) {
    New-Item -ItemType Directory -Force -Path $artifactsDir | Out-Null
}
$logPath = Join-Path $artifactsDir "preflight_$projectName.log"

# Header log
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"============================================================" | Out-File $logPath
"PYTHONPRO - Preflight Port Check" | Out-File $logPath -Append
"============================================================" | Out-File $logPath -Append
"Timestamp: $timestamp" | Out-File $logPath -Append
"Project: $projectName" | Out-File $logPath -Append
"Ports to check: $($ports -join ', ')" | Out-File $logPath -Append
"============================================================`n" | Out-File $logPath -Append

Write-Host "🔍 Preflight check per $projectName..." -ForegroundColor Cyan
Write-Host "   Porte da verificare: $($ports -join ', ')" -ForegroundColor Gray

$conflicts = @()
$conflictDetails = @()

foreach ($port in $ports) {
    try {
        $connections = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue

        if ($connections) {
            $conflicts += $port

            foreach ($conn in $connections) {
                $process = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
                if ($process) {
                    $detail = "Port $port in uso da: $($process.ProcessName) (PID: $($process.Id))"
                    $conflictDetails += $detail
                    "❌ $detail" | Out-File $logPath -Append
                    Write-Host "   ❌ $detail" -ForegroundColor Red
                }
            }
        } else {
            "✅ Port $port è libera" | Out-File $logPath -Append
            Write-Host "   ✅ Port $port è libera" -ForegroundColor Green
        }
    } catch {
        "⚠️  Errore verifica porta ${port}: $($_.Exception.Message)" | Out-File $logPath -Append
        Write-Warning "   Errore verifica porta $port"
    }
}

"`n============================================================" | Out-File $logPath -Append

if ($conflicts.Count -gt 0) {
    "❌ PREFLIGHT FALLITO" | Out-File $logPath -Append
    "Porte occupate: $($conflicts -join ', ')" | Out-File $logPath -Append
    "============================================================" | Out-File $logPath -Append

    Write-Host "`n❌ PREFLIGHT FALLITO!" -ForegroundColor Red
    Write-Host "   Porte occupate: $($conflicts -join ', ')" -ForegroundColor Yellow
    Write-Host "`n💡 Soluzioni:" -ForegroundColor Cyan
    Write-Host "   1. Ferma i processi che occupano le porte" -ForegroundColor Gray
    Write-Host "   2. Modifica le porte in .env" -ForegroundColor Gray
    Write-Host "   3. Log completo: $logPath" -ForegroundColor Gray
    Write-Host ""

    exit 2
} else {
    "✅ PREFLIGHT OK - Tutte le porte sono libere" | Out-File $logPath -Append
    "============================================================" | Out-File $logPath -Append

    Write-Host "`n✅ PREFLIGHT OK - Stack pronto per l'avvio!" -ForegroundColor Green
    Write-Host "   Log: $logPath" -ForegroundColor Gray
    Write-Host ""

    exit 0
}
