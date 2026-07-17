#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if find "$ROOT" -maxdepth 1 -name '.env.bak_*' | grep -q .; then
  echo "ERROR: .env.bak_* files still present" >&2
  exit 1
fi

required_keys=(
  JWT_SECRET_KEY
  DB_PASSWORD
  DB_MIGRATION_PASSWORD
  DB_APP_PASSWORD
  REDIS_PASSWORD
  BACKUP_ENCRYPTION_KEY
  OPENCLAW_API_KEY
  GMAIL_IMAP_APP_PASSWORD
  SMTP_PASSWORD
  ADMIN_DEFAULT_PASSWORD
  OPERATOR_DEFAULT_PASSWORD
  WHATSAPP_META_WEBHOOK_VERIFY_TOKEN
  WHATSAPP_META_APP_SECRET
)

for key in "${required_keys[@]}"; do
  grep -q "^${key}=" "$ROOT/.env.example" || { echo "ERROR: missing ${key} in .env.example" >&2; exit 1; }
done

for value in Admin2026! changeme_in_production changeme_redis_pwd your-app-specific-password your-super-secret-key-change-in-production; do
  if grep -q "$value" "$ROOT/.env.example" "$ROOT/backend/reset_password.py"; then
    echo "ERROR: forbidden secret-like value found: $value" >&2
    exit 1
  fi
done

development_sample="$ROOT/.env.development.sample"
for key in DB_PASSWORD REDIS_PASSWORD JWT_SECRET_KEY; do
  grep -q "^${key}=CHANGE_ME_" "$development_sample" || {
    echo "ERROR: ${key} in .env.development.sample is not an explicit placeholder" >&2
    exit 1
  }
done

for value in dev_password_123 dev_redis_123; do
  matches="$(git -C "$ROOT" grep -l -F "$value" -- \
    ':!audit/ANALISI_ARCHITETTURA_2026-07-17.md' \
    ':!audit/FINDINGS_NUOVI.md' \
    ':!scripts/check_secret_remediation.sh' || true)"
  if [[ -n "$matches" ]]; then
    echo "ERROR: deprecated development credential still present in tracked files" >&2
    echo "$matches" >&2
    exit 1
  fi
done

backup_line='BACKUP_ENCRYPTION_KEY: ${BACKUP_ENCRYPTION_KEY:?ERRORE_BACKUP_ENCRYPTION_KEY_OBBLIGATORIA}'
if [[ "$(grep -F -c "$backup_line" "$ROOT/docker-compose.yml")" -lt 2 ]]; then
  echo "ERROR: BACKUP_ENCRYPTION_KEY is not passed to backend and backup scheduler" >&2
  exit 1
fi

grep -q 'require_nodefault "BACKUP_ENCRYPTION_KEY"' "$ROOT/backend/scripts/validate_env.sh"
