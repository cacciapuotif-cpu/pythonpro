#!/usr/bin/env bash
# validate_env.sh — fail-fast check of required env vars before container startup
# Exit code 0 = all OK, 1 = one or more missing/invalid

set -euo pipefail

ERRORS=0

require_var() {
    local name="$1"
    local value="${!name:-}"
    if [[ -z "$value" ]]; then
        echo "ERROR: required env var '$name' is not set or empty" >&2
        ERRORS=$((ERRORS + 1))
    fi
}

require_nodefault() {
    # Same as require_var but also rejects obvious placeholder values
    local name="$1"
    local value="${!name:-}"
    local bad_values=("changeme" "secret" "placeholder" "example" "todo" "fixme" "your_" "insert_")
    if [[ -z "$value" ]]; then
        echo "ERROR: required env var '$name' is not set or empty" >&2
        ERRORS=$((ERRORS + 1))
        return
    fi
    for bad in "${bad_values[@]}"; do
        if [[ "${value,,}" == *"$bad"* ]]; then
            echo "ERROR: env var '$name' looks like a placeholder value: '$value'" >&2
            ERRORS=$((ERRORS + 1))
            return
        fi
    done
}

# ── Core app ────────────────────────────────────────────────────────────────
require_nodefault "JWT_SECRET_KEY"
require_nodefault "SECRET_KEY"
require_var       "DATABASE_URL"
require_var       "ENVIRONMENT"

# ── Default passwords (must be set, but can be any value — enforced by RBAC) ─
require_var "ADMIN_DEFAULT_PASSWORD"
require_var "OPERATOR_DEFAULT_PASSWORD"

# ── JWT_SECRET_KEY minimum length check (≥ 32 chars) ────────────────────────
jwt_key="${JWT_SECRET_KEY:-}"
jwt_len="${#jwt_key}"
if [[ "$jwt_len" -lt 32 ]]; then
    echo "ERROR: JWT_SECRET_KEY must be at least 32 characters (got $jwt_len)" >&2
    ERRORS=$((ERRORS + 1))
fi

# ── SMTP: if host is set, user and password are required ─────────────────────
if [[ -n "${SMTP_HOST:-}" ]]; then
    require_var "SMTP_USER"
    require_var "SMTP_PASSWORD"
fi

# ── WhatsApp: if enabled, critical vars must be present ─────────────────────
if [[ "${ENABLE_WHATSAPP:-false}" == "true" ]]; then
    require_var "WHATSAPP_META_PHONE_NUMBER_ID"
    require_var "WHATSAPP_API_TOKEN"
    require_var "WHATSAPP_META_WEBHOOK_VERIFY_TOKEN"
    require_nodefault "WHATSAPP_META_APP_SECRET"
fi

# ── Production-only checks ───────────────────────────────────────────────────
if [[ "${ENVIRONMENT:-}" == "production" ]]; then
    if [[ "${SMTP_TEST_MODE:-false}" == "true" ]]; then
        echo "ERROR: SMTP_TEST_MODE=true is not allowed in ENVIRONMENT=production" >&2
        ERRORS=$((ERRORS + 1))
    fi
    if [[ "${AUTO_BACKUP_ENABLED:-false}" != "true" ]]; then
        echo "WARNING: AUTO_BACKUP_ENABLED is not true in production — backups disabled" >&2
    fi
fi

# ── Result ───────────────────────────────────────────────────────────────────
if [[ "$ERRORS" -gt 0 ]]; then
    echo "validate_env.sh: $ERRORS error(s) found — refusing to start" >&2
    exit 1
fi

echo "validate_env.sh: all required env vars OK"
exit 0
