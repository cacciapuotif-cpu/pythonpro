#!/usr/bin/env bash
#
# Rebuild rapido di un singolo servizio (backend o frontend) che stampa
# comunque il commit reale — a differenza del comando ad-hoc finora
# documentato in docs/RUNBOOK_produzione.md, che non esporta APP_COMMIT/
# APP_BUILD_DATE e lascia quindi l'immagine con la label
# org.opencontainers.image.revision=unknown (il footer "Versione non
# disponibile" nasce da qui, non da un bug in Dockerfile/docker-compose.yml
# — quelli gia' stampano il commit giusto quando scripts/deploy.sh li build).
#
# Non e' un deploy atomico: nessun backup, nessuna migrazione, nessun
# rollback. Per un deploy reale usa scripts/deploy.sh. Questo script serve
# solo a far si' che anche un rebuild rapido durante lo sviluppo stampi il
# commit corretto, invece di richiedere di ricordarsi un export a mano.

set -Eeuo pipefail

SERVICE="${1:-}"
if [[ "${SERVICE}" != "backend" && "${SERVICE}" != "frontend" ]]; then
  echo "Uso: $(basename "$0") <backend|frontend>" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${PYTHONPRO_ENV_FILE:-${ROOT_DIR}/.env}"
DOCKER_CONFIG="${DOCKER_CONFIG:-/tmp/pythonpro-docker-config}"
export DOCKER_CONFIG
DOCKER_BUILDKIT="${DOCKER_BUILDKIT:-0}"
COMPOSE_BAKE="${COMPOSE_BAKE:-false}"
export DOCKER_BUILDKIT COMPOSE_BAKE

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERRORE: file ambiente non trovato: ${ENV_FILE}" >&2
  exit 1
fi

read_env_value() {
  local key="$1"
  local fallback="$2"
  local value
  value="$(awk -F= -v key="${key}" '$1 == key {sub(/^[^=]*=/, ""); print; exit}' "${ENV_FILE}")"
  printf '%s' "${value:-${fallback}}"
}

REBUILD_COMMIT="$(git -C "${ROOT_DIR}" rev-parse HEAD)"
REBUILD_BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
export APP_COMMIT="${REBUILD_COMMIT}"
export APP_BUILD_DATE="${REBUILD_BUILD_DATE}"

log() {
  printf '[rebuild-service] %s\n' "$*"
}

COMPOSE=(docker compose --project-name pythonpro --env-file "${ENV_FILE}" -f "${ROOT_DIR}/docker-compose.yml")
CONTAINER="pythonpro_${SERVICE}"
IMAGE="pythonpro-${SERVICE}"

log "Commit da stampare: ${REBUILD_COMMIT}"
"${COMPOSE[@]}" build "${SERVICE}"
"${COMPOSE[@]}" up -d --no-deps --force-recreate "${SERVICE}"

elapsed=0
timeout_seconds=180
state=""
while (( elapsed < timeout_seconds )); do
  state="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${CONTAINER}" 2>/dev/null || true)"
  if [[ "${state}" == "healthy" || "${state}" == "running" ]]; then
    break
  fi
  if [[ "${state}" == "unhealthy" || "${state}" == "exited" || "${state}" == "dead" ]]; then
    docker logs --tail 80 "${CONTAINER}" >&2 || true
    echo "ERRORE: ${CONTAINER} non e' salito correttamente (stato: ${state})" >&2
    exit 1
  fi
  sleep 2
  elapsed=$((elapsed + 2))
done
if [[ "${state}" != "healthy" && "${state}" != "running" ]]; then
  echo "ERRORE: timeout health per ${CONTAINER}" >&2
  exit 1
fi
log "${CONTAINER}: ${state}"

# Verifica lo stamp del commit — questo e' il controllo che manca anche a
# scripts/deploy.sh per il frontend: li' viene verificato solo /health del
# backend, mai la label dell'immagine frontend.
IMAGE_REVISION="$(docker inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "${CONTAINER}")"
if [[ "${IMAGE_REVISION}" != "${REBUILD_COMMIT}" ]]; then
  echo "ERRORE: ${CONTAINER} ha stampato il commit '${IMAGE_REVISION}', atteso '${REBUILD_COMMIT}'" >&2
  exit 1
fi
log "Label immagine ${IMAGE}: revision=${IMAGE_REVISION}"

if [[ "${SERVICE}" == "backend" ]]; then
  BACKEND_PORT_VALUE="$(read_env_value BACKEND_PORT 8001)"
  HEALTH_BODY="$(curl -fsS "http://127.0.0.1:${BACKEND_PORT_VALUE}/health")"
  if ! printf '%s' "${HEALTH_BODY}" | grep -q "${REBUILD_COMMIT}"; then
    echo "ERRORE: /health non espone il commit distribuito (${REBUILD_COMMIT})" >&2
    echo "${HEALTH_BODY}" >&2
    exit 1
  fi
  log "/health espone il commit corretto"
fi

log "Rebuild ${SERVICE} completato: commit ${REBUILD_COMMIT} verificato"
