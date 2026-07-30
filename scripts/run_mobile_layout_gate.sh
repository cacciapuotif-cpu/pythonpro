#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_ROOT="$REPO_ROOT/frontend"
PLAYWRIGHT_IMAGE="mcr.microsoft.com/playwright:v1.59.1-noble"
MOB_DOCKER_CONFIG="/tmp/pythonpro-mobile-docker-config"

mkdir -p "$MOB_DOCKER_CONFIG"
export DOCKER_CONFIG="$MOB_DOCKER_CONFIG"

node "$FRONTEND_ROOT/scripts/check-responsive-contract.js"

MOB_E2E_TOKEN="$(docker exec pythonpro_backend python -c "
from datetime import timedelta
from auth import SecurityUtils, User
from database import SessionLocal
import models  # registra tutte le relazioni SQLAlchemy prima della query User
db = SessionLocal()
try:
    user = db.query(User).filter(User.username == 'ui_test_admin').one()
    print(SecurityUtils.generate_token(
        data={
            'sub': user.username,
            'type': 'access',
            'role': user.role,
            'credential_marker': SecurityUtils.credential_marker(user.hashed_password),
        },
        expires_delta=timedelta(minutes=45),
    ))
finally:
    db.close()
")"
export E2E_ACCESS_TOKEN="$MOB_E2E_TOKEN"
export BASE_URL="${BASE_URL:-http://localhost:3001}"

docker run --rm --network host --ipc=host --tmpfs /tmp:rw,exec,mode=1777 \
  -e E2E_ACCESS_TOKEN \
  -e BASE_URL \
  -e RESPONSIVE_ARTIFACT_DIR=/work/test-results/responsive-layout \
  -v "$FRONTEND_ROOT:/work" \
  -w /work \
  "$PLAYWRIGHT_IMAGE" \
  node e2e/responsive-layout.js

unset E2E_ACCESS_TOKEN MOB_E2E_TOKEN
