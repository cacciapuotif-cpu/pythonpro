#!/bin/bash
# ============================================================
# 🧪 BACKEND SMOKE TEST (Bash)
# ============================================================
# Test minimale backend per CI/CD o Linux
# ============================================================

set -e

echo "🧪 Backend Smoke Test"
echo "=================================="

# Test 1: Health endpoint
echo -n "Test 1: /health endpoint... "
RESPONSE=$(curl -s -w "%{http_code}" -o /tmp/health.json http://localhost:8000/health)
if [ "$RESPONSE" = "200" ]; then
    echo "✅ PASS"
    cat /tmp/health.json | python3 -m json.tool
else
    echo "❌ FAIL (HTTP $RESPONSE)"
    exit 1
fi

echo ""
echo "✅ Tutti i test passati!"
