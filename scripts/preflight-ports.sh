#!/usr/bin/env bash
# ============================================================
# PYTHONPRO - Preflight Port Check (Bash)
# ============================================================
# Verifica che tutte le porte richieste siano libere prima
# di avviare lo stack Docker
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_ROOT/.env"

# Verifica esistenza .env
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ File .env non trovato in: $PROJECT_ROOT"
    exit 1
fi

# Leggi variabili d'ambiente
source "$ENV_FILE"

PROJECT_NAME="${COMPOSE_PROJECT_NAME:-pythonpro}"
PORTS=("${FRONTEND_PORT}" "${BACKEND_PORT}" "${POSTGRES_PORT}" "${REDIS_PORT}")

# Prepara log
ARTIFACTS_DIR="$PROJECT_ROOT/artifacts"
mkdir -p "$ARTIFACTS_DIR"
LOG_FILE="$ARTIFACTS_DIR/preflight_${PROJECT_NAME}.log"

# Header log
{
    echo "============================================================"
    echo "PYTHONPRO - Preflight Port Check"
    echo "============================================================"
    echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Project: $PROJECT_NAME"
    echo "Ports to check: ${PORTS[*]}"
    echo "============================================================"
    echo ""
} > "$LOG_FILE"

echo "🔍 Preflight check per $PROJECT_NAME..."
echo "   Porte da verificare: ${PORTS[*]}"

CONFLICTS=()
CONFLICT_DETAILS=()

for port in "${PORTS[@]}"; do
    if [ -z "$port" ]; then
        continue
    fi

    # Verifica se la porta è in uso
    if command -v lsof &> /dev/null; then
        PROCESS=$(lsof -ti :$port 2>/dev/null || true)
    elif command -v netstat &> /dev/null; then
        PROCESS=$(netstat -tlnp 2>/dev/null | grep ":$port " | awk '{print $7}' | cut -d'/' -f1 || true)
    else
        echo "⚠️  Comando lsof/netstat non disponibile" | tee -a "$LOG_FILE"
        continue
    fi

    if [ -n "$PROCESS" ]; then
        CONFLICTS+=("$port")
        DETAIL="Port $port in uso da PID: $PROCESS"
        CONFLICT_DETAILS+=("$DETAIL")
        echo "❌ $DETAIL" | tee -a "$LOG_FILE"
        echo "   ❌ $DETAIL"
    else
        echo "✅ Port $port è libera" >> "$LOG_FILE"
        echo "   ✅ Port $port è libera"
    fi
done

echo "" >> "$LOG_FILE"
echo "============================================================" >> "$LOG_FILE"

if [ ${#CONFLICTS[@]} -gt 0 ]; then
    echo "❌ PREFLIGHT FALLITO" | tee -a "$LOG_FILE"
    echo "Porte occupate: ${CONFLICTS[*]}" | tee -a "$LOG_FILE"
    echo "============================================================" >> "$LOG_FILE"

    echo ""
    echo "❌ PREFLIGHT FALLITO!"
    echo "   Porte occupate: ${CONFLICTS[*]}"
    echo ""
    echo "💡 Soluzioni:"
    echo "   1. Ferma i processi che occupano le porte"
    echo "   2. Modifica le porte in .env"
    echo "   3. Log completo: $LOG_FILE"
    echo ""

    exit 2
else
    echo "✅ PREFLIGHT OK - Tutte le porte sono libere" | tee -a "$LOG_FILE"
    echo "============================================================" >> "$LOG_FILE"

    echo ""
    echo "✅ PREFLIGHT OK - Stack pronto per l'avvio!"
    echo "   Log: $LOG_FILE"
    echo ""

    exit 0
fi
