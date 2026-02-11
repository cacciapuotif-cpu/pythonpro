#!/usr/bin/env bash
#
# Stop production PythonPro stack
#

set -euo pipefail

echo "Stopping PythonPro production stack..."
cd "$(dirname "$0")/.."
docker compose -f docker-compose.prod.yml down

echo "✅ Stack stopped"
