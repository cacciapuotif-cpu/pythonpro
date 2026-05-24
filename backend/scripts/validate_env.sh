#!/usr/bin/env bash
set -euo pipefail

REQUIRED_VARS=(
  "JWT_SECRET_KEY"
  "DB_PASSWORD"
  "REDIS_PASSWORD"
  "ADMIN_DEFAULT_PASSWORD"
  "CORS_ALLOWED_ORIGINS"
  "SMTP_HOST"
  "SMTP_USER"
  "SMTP_PASSWORD"
)

SECRET_VARS=(
  "JWT_SECRET_KEY"
  "DB_PASSWORD"
  "REDIS_PASSWORD"
  "ADMIN_DEFAULT_PASSWORD"
  "SMTP_PASSWORD"
)

for var_name in "${REQUIRED_VARS[@]}"; do
  value="${!var_name:-}"
  if [ -z "$value" ]; then
    echo "ERRORE AVVIO: ${var_name} non configurata" >&2
    exit 1
  fi
done

for var_name in "${SECRET_VARS[@]}"; do
  value="${!var_name:-}"
  if [ "${#value}" -lt 16 ]; then
    echo "ERRORE AVVIO: ${var_name} troppo corta (minimo 16 caratteri)" >&2
    exit 1
  fi
done

if [ "${SMTP_TEST_MODE:-false}" = "true" ] && [ "${ENVIRONMENT:-production}" = "production" ]; then
  echo "ERRORE AVVIO: SMTP_TEST_MODE=true non ammesso in produzione" >&2
  exit 1
fi

echo "Variabili d'ambiente: OK"
