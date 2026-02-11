# ============================================================
# 🚀 AVVIO STACK PRODUZIONE
# ============================================================
# Avvia lo stack con profilo produzione
# REQUISITO: file .env con password sicure!
# ============================================================

Write-Host "🚀 Avvio stack PRODUZIONE..." -ForegroundColor Magenta
Write-Host ""

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
Set-Location $projectRoot

# Verifica esistenza .env
if (-not (Test-Path ".env")) {
    Write-Host "❌ ERRORE: File .env non trovato!" -ForegroundColor Red
    Write-Host "   Crea .env da .env.sample con password sicure" -ForegroundColor Yellow
    Write-Host "   cp .env.sample .env" -ForegroundColor Gray
    exit 1
}

# Verifica password di default
$envContent = Get-Content ".env" -Raw
if ($envContent -match "changeme") {
    Write-Host "⚠️  ATTENZIONE: File .env contiene password di default 'changeme'" -ForegroundColor Yellow
    Write-Host "   Genera password sicure prima di usare in produzione!" -ForegroundColor Yellow
    Write-Host ""
    $confirm = Read-Host "Continuare comunque? (y/N)"
    if ($confirm -ne "y") {
        exit 1
    }
}

docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

Write-Host ""
Write-Host "✅ Stack produzione avviato" -ForegroundColor Green
Write-Host "   Verifica health: docker compose ps" -ForegroundColor White
