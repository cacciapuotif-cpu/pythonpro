#!/usr/bin/env bash
#
# Start production PythonPro stack
#

set -euo pipefail

echo "=================================================="
echo " Starting PythonPro Production Stack"
echo "=================================================="
echo ""

# Change to repo root
cd "$(dirname "$0")/.."

# Check if images exist
if ! docker images | grep -q "pythonpro.*backend"; then
    echo "⚠️  Backend image not found. Building images first..."
    bash scripts/build-prod.sh
fi

echo "Starting services..."
docker compose -f docker-compose.prod.yml up -d

echo ""
echo "Waiting for services to be healthy..."
sleep 5

echo ""
echo "=================================================="
echo " ✅ Stack is starting!"
echo "=================================================="
echo ""
echo "Service status:"
docker compose -f docker-compose.prod.yml ps

echo ""
echo "Access the application:"
echo "  Frontend: http://localhost/"
echo "  API:      http://localhost/api/v1/"
echo "  Health:   http://localhost/healthz"
echo ""
echo "View logs:"
echo "  docker compose -f docker-compose.prod.yml logs -f"
echo ""
echo "Stop services:"
echo "  docker compose -f docker-compose.prod.yml down"
echo ""
