#!/usr/bin/env bash

# Deploy atomico PythonPro.
#
# Flusso: backup verificato -> snapshot immagini -> build da Git HEAD ->
# migrate -> restart ordinato -> health/smoke. Qualunque errore dopo la build
# ripristina automaticamente immagini e, solo se la revisione Alembic e'
# cambiata, il database dal backup pre-deploy.

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${PYTHONPRO_ENV_FILE:-${ROOT_DIR}/.env}"
DOCKER_CONFIG="${DOCKER_CONFIG:-/tmp/pythonpro-docker-config}"
export DOCKER_CONFIG

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERRORE: file ambiente non trovato: ${ENV_FILE}" >&2
  exit 1
fi

for command_name in docker git tar curl; do
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "ERRORE: comando richiesto non disponibile: ${command_name}" >&2
    exit 1
  fi
done

mkdir -p "${DOCKER_CONFIG}" "${ROOT_DIR}/artifacts/deployments"

DEPLOY_COMMIT="$(git -C "${ROOT_DIR}" rev-parse HEAD)"
DEPLOY_SHORT="$(git -C "${ROOT_DIR}" rev-parse --short=12 HEAD)"
DEPLOY_BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
DEPLOY_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RELEASE_DIR="$(mktemp -d /tmp/pythonpro-release.XXXXXX)"
MANIFEST="${ROOT_DIR}/artifacts/deployments/${DEPLOY_STAMP}_${DEPLOY_SHORT}.env"

export APP_COMMIT="${DEPLOY_COMMIT}"
export APP_BUILD_DATE="${DEPLOY_BUILD_DATE}"

declare -a SERVICES=(backend arq_worker backup_scheduler check_scadenze_scheduler frontend)
declare -A CONTAINERS=(
  [backend]=pythonpro_backend
  [arq_worker]=pythonpro_arq_worker
  [backup_scheduler]=pythonpro_backup_scheduler
  [check_scadenze_scheduler]=pythonpro_check_scadenze_scheduler
  [frontend]=pythonpro_frontend
)
declare -A IMAGES=(
  [backend]=pythonpro-backend
  [arq_worker]=pythonpro-arq_worker
  [backup_scheduler]=pythonpro-backup_scheduler
  [check_scadenze_scheduler]=pythonpro-check_scadenze_scheduler
  [frontend]=pythonpro-frontend
)
declare -A OLD_IMAGE_IDS=()

DEPLOY_MUTATED=0
DB_CHANGED=0
BACKUP_PATH=""
PRE_DB_REVISION=""
TARGET_DB_REVISION=""
OLD_AGENT_FLAGS=""

log() {
  printf '[deploy] %s\n' "$*"
}

cleanup() {
  if [[ "${RELEASE_DIR}" == /tmp/pythonpro-release.* && -d "${RELEASE_DIR}" ]]; then
    rm -rf -- "${RELEASE_DIR}"
  fi
}

read_env_value() {
  local key="$1"
  local fallback="$2"
  local value
  value="$(awk -F= -v key="${key}" '$1 == key {sub(/^[^=]*=/, ""); print; exit}' "${ENV_FILE}")"
  printf '%s' "${value:-${fallback}}"
}

BACKEND_PORT_VALUE="$(read_env_value BACKEND_PORT 8001)"
FRONTEND_PORT_VALUE="$(read_env_value FRONTEND_PORT 3001)"
BACKEND_URL="http://127.0.0.1:${BACKEND_PORT_VALUE}"
FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT_VALUE}"

wait_healthy() {
  local container="$1"
  local timeout_seconds="${2:-180}"
  local elapsed=0
  local state
  while (( elapsed < timeout_seconds )); do
    state="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${container}" 2>/dev/null || true)"
    if [[ "${state}" == "healthy" || "${state}" == "running" ]]; then
      log "${container}: ${state}"
      return 0
    fi
    if [[ "${state}" == "unhealthy" || "${state}" == "exited" || "${state}" == "dead" ]]; then
      docker logs --tail 80 "${container}" >&2 || true
      return 1
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  docker logs --tail 80 "${container}" >&2 || true
  echo "ERRORE: timeout health per ${container}" >&2
  return 1
}

restore_previous_release() {
  local reason="$1"
  set +e
  trap - ERR
  log "ROLLBACK automatico: ${reason}"

  "${COMPOSE[@]}" stop frontend check_scadenze_scheduler backup_scheduler arq_worker backend >/dev/null 2>&1

  if [[ "${DB_CHANGED}" == "1" && -n "${BACKUP_PATH}" ]]; then
    log "Ripristino DB da ${BACKUP_PATH}"
    "${COMPOSE[@]}" run --rm --no-deps \
      -e "DEPLOY_ROLLBACK_BACKUP=${BACKUP_PATH}" \
      --entrypoint python backup_scheduler -c \
      'import os; from backup_manager import get_backup_manager; raise SystemExit(0 if get_backup_manager().restore_backup(os.environ["DEPLOY_ROLLBACK_BACKUP"]) else 1)'
  fi

  for service in "${SERVICES[@]}"; do
    if [[ -n "${OLD_IMAGE_IDS[${service}]:-}" ]]; then
      docker image tag "${IMAGES[${service}]}:rollback-${DEPLOY_STAMP}" "${IMAGES[${service}]}:latest"
    fi
  done

  "${COMPOSE[@]}" up -d --no-deps --force-recreate backend
  wait_healthy pythonpro_backend 180
  "${COMPOSE[@]}" up -d --no-deps --force-recreate arq_worker backup_scheduler check_scadenze_scheduler
  wait_healthy pythonpro_arq_worker 120
  "${COMPOSE[@]}" up -d --no-deps --force-recreate frontend
  wait_healthy pythonpro_frontend 120
  log "Rollback completato"
  set -e
}

on_error() {
  local exit_code="$1"
  local line_number="$2"
  if [[ "${DEPLOY_MUTATED}" == "1" ]]; then
    restore_previous_release "errore rc=${exit_code} alla linea ${line_number}"
  fi
  exit "${exit_code}"
}

trap 'on_error $? $LINENO' ERR
trap cleanup EXIT

log "Commit da distribuire: ${DEPLOY_COMMIT}"
if [[ -n "$(git -C "${ROOT_DIR}" status --porcelain)" ]]; then
  log "Worktree sporca rilevata: il deploy usera' solo il contenuto committato di Git HEAD"
fi

git -C "${ROOT_DIR}" archive "${DEPLOY_COMMIT}" | tar -x -C "${RELEASE_DIR}"

COMPOSE=(
  docker compose
  --project-name pythonpro
  --env-file "${ENV_FILE}"
  -f "${RELEASE_DIR}/docker-compose.yml"
  -f "${RELEASE_DIR}/docker-compose.deploy.yml"
)

"${COMPOSE[@]}" config > "${RELEASE_DIR}/compose.rendered.yml"
if grep -q 'type: bind' "${RELEASE_DIR}/compose.rendered.yml"; then
  echo "ERRORE: il profilo deploy contiene ancora bind mount" >&2
  exit 1
fi

PRE_DB_REVISION="$(docker exec pythonpro_backend alembic current 2>/dev/null | awk '/^[0-9]+/{print $1; exit}')"
OLD_AGENT_FLAGS="$(docker exec pythonpro_backend sh -c 'printf "%s|%s|%s|%s" "$AGENTS_ENABLED" "$AGENT_EMAIL_INTAKE_ENABLED" "$AGENT_DATA_RETENTION_ENABLED" "$ENABLE_WHATSAPP"')"

log "Creazione backup pre-deploy cifrato e verifica integrita'"
BACKUP_OUTPUT="$(docker exec pythonpro_backup_scheduler python -c '
from backup_manager import get_backup_manager
m = get_backup_manager()
p = m.create_backup("pre_deploy")
assert p, "creazione backup fallita"
assert m.verify_backup_integrity(p), "verifica backup fallita"
print("DEPLOY_BACKUP=" + p)
')"
BACKUP_PATH="$(printf '%s\n' "${BACKUP_OUTPUT}" | awk -F= '/^DEPLOY_BACKUP=/{print $2; exit}')"
if [[ -z "${BACKUP_PATH}" ]]; then
  echo "ERRORE: percorso backup non rilevato" >&2
  exit 1
fi
log "Backup verificato: ${BACKUP_PATH}"

for service in "${SERVICES[@]}"; do
  container="${CONTAINERS[${service}]}"
  OLD_IMAGE_IDS[${service}]="$(docker inspect --format '{{.Image}}' "${container}")"
  docker image tag "${OLD_IMAGE_IDS[${service}]}" "${IMAGES[${service}]}:rollback-${DEPLOY_STAMP}"
done

{
  printf 'DEPLOY_COMMIT=%s\n' "${DEPLOY_COMMIT}"
  printf 'DEPLOY_BUILD_DATE=%s\n' "${DEPLOY_BUILD_DATE}"
  printf 'BACKUP_PATH=%s\n' "${BACKUP_PATH}"
  printf 'PRE_DB_REVISION=%s\n' "${PRE_DB_REVISION}"
  for service in "${SERVICES[@]}"; do
    printf 'OLD_IMAGE_%s=%s\n' "${service^^}" "${OLD_IMAGE_IDS[${service}]}"
  done
} > "${MANIFEST}"

DEPLOY_MUTATED=1
log "Build immagini immutabili da Git HEAD"
"${COMPOSE[@]}" build backend arq_worker backup_scheduler check_scadenze_scheduler frontend

for service in "${SERVICES[@]}"; do
  docker image tag "${IMAGES[${service}]}:latest" "${IMAGES[${service}]}:${DEPLOY_SHORT}"
done

TARGET_DB_REVISION="$("${COMPOSE[@]}" run --rm --no-deps --entrypoint alembic backend heads | awk '/^[0-9]+/{print $1; exit}')"
log "Alembic: live=${PRE_DB_REVISION}, target=${TARGET_DB_REVISION}"
"${COMPOSE[@]}" run --rm --no-deps --entrypoint alembic backend upgrade head
if [[ "${PRE_DB_REVISION}" != "${TARGET_DB_REVISION}" ]]; then
  DB_CHANGED=1
fi

log "Restart ordinato backend -> worker/scheduler -> frontend"
"${COMPOSE[@]}" up -d --no-deps --force-recreate backend
wait_healthy pythonpro_backend 180

"${COMPOSE[@]}" up -d --no-deps --force-recreate arq_worker backup_scheduler check_scadenze_scheduler
wait_healthy pythonpro_arq_worker 120

"${COMPOSE[@]}" up -d --no-deps --force-recreate frontend
wait_healthy pythonpro_frontend 120

NEW_AGENT_FLAGS="$(docker exec pythonpro_backend sh -c 'printf "%s|%s|%s|%s" "$AGENTS_ENABLED" "$AGENT_EMAIL_INTAKE_ENABLED" "$AGENT_DATA_RETENTION_ENABLED" "$ENABLE_WHATSAPP"')"
if [[ "${NEW_AGENT_FLAGS}" != "${OLD_AGENT_FLAGS}" ]]; then
  echo "ERRORE: stato kill switch cambiato (${OLD_AGENT_FLAGS} -> ${NEW_AGENT_FLAGS})" >&2
  false
fi

for container in pythonpro_backend pythonpro_arq_worker; do
  if docker inspect "${container}" --format '{{range .Mounts}}{{.Type}} {{.Destination}}\n{{end}}' | grep -q '^bind ';
  then
    echo "ERRORE: ${container} usa ancora un bind mount" >&2
    false
  fi
done

HEALTH_BODY="$(curl -fsS "${BACKEND_URL}/health")"
if ! printf '%s' "${HEALTH_BODY}" | grep -q "${DEPLOY_COMMIT}"; then
  echo "ERRORE: /health non espone il commit distribuito" >&2
  false
fi

FRONTEND_INDEX="$(curl -fsS "${FRONTEND_URL}/")"
FRONTEND_BUNDLE="$(printf '%s' "${FRONTEND_INDEX}" | sed -nE 's#.*(static/js/main\.[a-z0-9]+\.js).*#\1#p' | head -1)"
if [[ -z "${FRONTEND_BUNDLE}" ]]; then
  echo "ERRORE: bundle frontend non rilevato" >&2
  false
fi
curl -fsS "${FRONTEND_URL}/${FRONTEND_BUNDLE}" -o "${RELEASE_DIR}/frontend-main.js"
if ! grep -q "${DEPLOY_SHORT}" "${RELEASE_DIR}/frontend-main.js"; then
  echo "ERRORE: bundle frontend senza marker commit ${DEPLOY_SHORT}" >&2
  false
fi

ADMIN_TOKEN="$(docker exec pythonpro_backend python -c '
from datetime import timedelta
from auth import SecurityUtils, User
from database import SessionLocal
db = SessionLocal()
user = db.query(User).filter(User.role == "admin", User.is_active.is_(True)).order_by(User.id).first()
assert user, "admin attivo non trovato"
print(SecurityUtils.generate_token(data={"sub": user.username, "type": "access", "role": user.role, "credential_marker": SecurityUtils.credential_marker(user.hashed_password)}, expires_delta=timedelta(minutes=10)))
db.close()
')"

for endpoint in '/api/v1/projects/?limit=200&is_active=true' '/api/v1/projects/11/moduli-formativi'; do
  status="$(curl -sS -o /dev/null -w '%{http_code}' -H "Authorization: Bearer ${ADMIN_TOKEN}" "${BACKEND_URL}${endpoint}")"
  if [[ "${status}" != "200" ]]; then
    echo "ERRORE: smoke ${endpoint} -> ${status}" >&2
    false
  fi
done

POST_DB_REVISION="$(docker exec pythonpro_backend alembic current 2>/dev/null | awk '/^[0-9]+/{print $1; exit}')"
if [[ "${POST_DB_REVISION}" != "${TARGET_DB_REVISION}" ]]; then
  echo "ERRORE: Alembic post-deploy ${POST_DB_REVISION}, atteso ${TARGET_DB_REVISION}" >&2
  false
fi

{
  printf 'POST_DB_REVISION=%s\n' "${POST_DB_REVISION}"
  for service in "${SERVICES[@]}"; do
    printf 'NEW_IMAGE_%s=%s\n' "${service^^}" "$(docker inspect --format '{{.Image}}' "${CONTAINERS[${service}]}")"
  done
  printf 'RESULT=success\n'
} >> "${MANIFEST}"

DEPLOY_MUTATED=0
log "DEPLOY RIUSCITO: commit ${DEPLOY_COMMIT}"
log "Manifest: ${MANIFEST}"
