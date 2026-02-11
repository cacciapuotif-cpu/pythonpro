#!/usr/bin/env bash
#
# Build production Docker images for pythonpro
#

set -euo pipefail

echo "=================================================="
echo " Building PythonPro Production Images"
echo "=================================================="
echo ""

# Change to repo root
cd "$(dirname "$0")/.."

echo "Building backend image..."
docker compose -f docker-compose.prod.yml build --no-cache backend

echo ""
echo "Building frontend image..."
docker compose -f docker-compose.prod.yml build --no-cache frontend

echo ""
echo "=================================================="
echo " ✅ Build complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "  1. Review environment variables in docker-compose.prod.yml"
echo "  2. Set SECRET_KEY and JWT_SECRET environment variables"
echo "  3. Run: bash scripts/up-prod.sh"
echo ""
