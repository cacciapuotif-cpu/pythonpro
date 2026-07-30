#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_ROOT="$REPO_ROOT/frontend"
PLAYWRIGHT_IMAGE="mcr.microsoft.com/playwright:v1.59.1-noble"
MOB_DOCKER_CONFIG="/tmp/pythonpro-mobile-docker-config"

mkdir -p "$MOB_DOCKER_CONFIG"
export DOCKER_CONFIG="$MOB_DOCKER_CONFIG"

E2E_ROLE_TOKENS="$(docker exec pythonpro_backend python -c "
from datetime import timedelta
import json
from auth import SecurityUtils, User
from database import SessionLocal
import models
db = SessionLocal()
try:
    result = {}
    for role, username in {
        'admin': 'ui_test_admin',
        'operatore': 'ui_test_operatore',
        'consultazione': 'ui_test_consultazione',
    }.items():
        user = db.query(User).filter(User.username == username).one()
        result[role] = SecurityUtils.generate_token(
            data={
                'sub': user.username,
                'type': 'access',
                'role': user.role,
                'credential_marker': SecurityUtils.credential_marker(user.hashed_password),
            },
            expires_delta=timedelta(minutes=45),
        )
    print(json.dumps(result))
finally:
    db.close()
")"

export E2E_ROLE_TOKENS
export BASE_URL="${BASE_URL:-http://localhost:3001}"

docker run --rm --network host --ipc=host --tmpfs /tmp:rw,exec,mode=1777 \
  -e E2E_ROLE_TOKENS \
  -e BASE_URL \
  -e MOB2_ARTIFACT_DIR=/work/test-results/mobile-navigation \
  -v "$FRONTEND_ROOT:/work" \
  -w /work \
  "$PLAYWRIGHT_IMAGE" \
  node e2e/mobile-navigation.js

unset E2E_ROLE_TOKENS
