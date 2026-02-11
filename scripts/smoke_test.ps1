# ============================================================
# 🧪 SMOKE TEST - Suite Test Minimale
# ============================================================
# Test rapidi per verificare che lo stack funzioni
#
# UTILIZZO:
#   .\scripts\smoke_test.ps1
# ============================================================

$ErrorActionPreference = "Continue"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "🧪 SMOKE TEST - Gestionale Pythonpro" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$tests_passed = 0
$tests_failed = 0

# === FUNZIONI ===
function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Url,
        [int]$ExpectedStatus = 200
    )

    Write-Host "TEST: $Name" -ForegroundColor Yellow -NoNewline

    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 10
        if ($response.StatusCode -eq $ExpectedStatus) {
            Write-Host " ✅ PASS" -ForegroundColor Green
            Write-Host "   Status: $($response.StatusCode), Content-Length: $($response.Content.Length)" -ForegroundColor DarkGray
            return $true
        } else {
            Write-Host " ❌ FAIL" -ForegroundColor Red
            Write-Host "   Expected: $ExpectedStatus, Got: $($response.StatusCode)" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host " ❌ FAIL" -ForegroundColor Red
        Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

function Test-Container {
    param([string]$Name)

    Write-Host "TEST: Container $Name" -ForegroundColor Yellow -NoNewline

    $status = docker inspect --format='{{.State.Status}}' $Name 2>$null
    $health = docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' $Name 2>$null

    if ($status -eq "running") {
        if ($health -eq "healthy" -or $health -eq "no-healthcheck") {
            Write-Host " ✅ PASS" -ForegroundColor Green
            Write-Host "   Status: $status, Health: $health" -ForegroundColor DarkGray
            return $true
        } else {
            Write-Host " ⚠️  WARNING" -ForegroundColor Yellow
            Write-Host "   Status: $status, Health: $health (not healthy yet)" -ForegroundColor Yellow
            return $true
        }
    } else {
        Write-Host " ❌ FAIL" -ForegroundColor Red
        Write-Host "   Status: $status" -ForegroundColor Red
        return $false
    }
}

# === TEST 1: Docker Running ===
Write-Host "[1/8] Docker Daemon" -ForegroundColor Cyan
try {
    docker info | Out-Null
    Write-Host "   ✅ Docker daemon running" -ForegroundColor Green
    $tests_passed++
} catch {
    Write-Host "   ❌ Docker daemon not running" -ForegroundColor Red
    $tests_failed++
}
Write-Host ""

# === TEST 2-5: Containers ===
Write-Host "[2/8] Container Status" -ForegroundColor Cyan
if (Test-Container "gestionale_db") { $tests_passed++ } else { $tests_failed++ }
if (Test-Container "gestionale_redis") { $tests_passed++ } else { $tests_failed++ }
if (Test-Container "gestionale_backend") { $tests_passed++ } else { $tests_failed++ }
if (Test-Container "gestionale_frontend") { $tests_passed++ } else { $tests_failed++ }
Write-Host ""

# === TEST 6: Backend Health ===
Write-Host "[3/8] Backend Endpoints" -ForegroundColor Cyan
if (Test-Endpoint "Backend /health" "http://localhost:8000/health") { $tests_passed++ } else { $tests_failed++ }
Write-Host ""

# === TEST 7: Frontend ===
Write-Host "[4/8] Frontend" -ForegroundColor Cyan
if (Test-Endpoint "Frontend Homepage" "http://localhost:3001/") { $tests_passed++ } else { $tests_failed++ }
Write-Host ""

# === TEST 8: Proxy API ===
Write-Host "[5/8] Frontend → Backend Proxy" -ForegroundColor Cyan
if (Test-Endpoint "Proxy /api/health" "http://localhost:3001/api/health") { $tests_passed++ } else { $tests_failed++ }
Write-Host ""

# === SUMMARY ===
$total_tests = $tests_passed + $tests_failed

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "📊 RISULTATI" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Tests Passed:  $tests_passed / $total_tests" -ForegroundColor Green
Write-Host "Tests Failed:  $tests_failed / $total_tests" -ForegroundColor Red
Write-Host ""

if ($tests_failed -eq 0) {
    Write-Host "✅ TUTTI I TEST PASSATI!" -ForegroundColor Green
    Write-Host "   Lo stack è funzionante e pronto all'uso." -ForegroundColor Green
    exit 0
} else {
    Write-Host "❌ ALCUNI TEST FALLITI" -ForegroundColor Red
    Write-Host "   Verifica i log con: docker compose logs -f" -ForegroundColor Yellow
    exit 1
}
