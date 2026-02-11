# Avvia-Docker-Pulito.ps1
# Script per riavviare WSL e Docker in modo sicuro

Write-Host "🧹 Chiusura pulita WSL..." -ForegroundColor Cyan
wsl --shutdown

function Try-Restart($name) {
  try { Get-Service $name -ErrorAction Stop | Restart-Service -ErrorAction Stop } catch {}
}
Try-Restart "vmcompute"
Try-Restart "hns"

Write-Host "🚀 Avvio Docker Desktop..." -ForegroundColor Cyan
Start-Process -FilePath "$Env:ProgramFiles\Docker\Docker\Docker Desktop.exe"

Start-Sleep -Seconds 15

Write-Host "🔎 Verifiche veloci:" -ForegroundColor Yellow
wsl -l -v
docker version
docker info | Select-String -Pattern "Server Version","Operating System","OSType"
