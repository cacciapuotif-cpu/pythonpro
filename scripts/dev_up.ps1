# ============================================================
# 🔧 AVVIO RAPIDO SVILUPPO
# ============================================================
# Shortcut per avviare lo stack di sviluppo
# ============================================================

Write-Host "🔧 Avvio stack sviluppo..." -ForegroundColor Cyan
Write-Host ""

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
Set-Location $projectRoot

docker compose up -d --build

Write-Host ""
Write-Host "✅ Stack avviato. Controlla status con: docker compose ps" -ForegroundColor Green
Write-Host "   Frontend: http://localhost:3001" -ForegroundColor White
Write-Host "   Backend:  http://localhost:8001/docs" -ForegroundColor White
