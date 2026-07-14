import os
import sys
import types

# Test-only defaults: no production secrets, just deterministic dummy values.
os.environ.setdefault("SECRET_KEY", "TestSecretKey12345678901234567890!")
os.environ.setdefault("JWT_SECRET_KEY", "TestSecretKey12345678901234567890!")
os.environ.setdefault("ADMIN_DEFAULT_PASSWORD", "AdminTest123456!")
os.environ.setdefault("OPERATOR_DEFAULT_PASSWORD", "OperatorTest123456!")
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/pythonpro_test.db")
os.environ.setdefault("LOG_DIR", "/tmp/pythonpro_test_logs")
os.environ.setdefault("UPLOADS_DIR", "/tmp/pythonpro_test_uploads")
os.environ.setdefault("EXPORTS_DIR", "/tmp/pythonpro_test_exports")
os.environ["REDIS_HOST"] = "127.0.0.1"
os.environ["REDIS_PORT"] = "1"
os.environ.setdefault("REDIS_PASSWORD", "RedisTest123456!")
os.environ.setdefault("SMTP_HOST", "smtp.test.local")
os.environ.setdefault("SMTP_USER", "test@example.com")
os.environ.setdefault("SMTP_PASSWORD", "SmtpTest123456!")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost")
os.environ.setdefault("OPENCLAW_API_KEY", "OpenclawTest123456!")
os.environ.setdefault("WHATSAPP_META_WEBHOOK_VERIFY_TOKEN", "WebhookTest123456!")
os.environ.setdefault("WHATSAPP_META_APP_SECRET", "MetaAppSecretTest123456!")
os.environ.setdefault("ENVIRONMENT", "test")

# The legacy app.core.Settings model forbids unknown env vars. Remove compose-only
# variables during tests before app.main is imported.
for key in [
    "COMPOSE_PROJECT_NAME", "FRONTEND_PORT", "BACKEND_PORT", "POSTGRES_PORT",
    "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT", "WORKERS",
    "TIMEOUT", "GRACEFUL_TIMEOUT", "AI_AGENT_LLM_PROVIDER", "AI_AGENT_LLM_MODEL",
    "AI_AGENT_LLM_TIMEOUT_SECONDS", "OLLAMA_BASE_URL", "OPENCLAW_BASE_URL",
    "OPENCLAW_CHAT_PATH", "GMAIL_IMAP_USER", "GMAIL_IMAP_APP_PASSWORD",
    "INBOX_POLL_INTERVAL_SECONDS",
]:
    os.environ.pop(key, None)

arq_module = types.ModuleType("arq")
arq_connections = types.ModuleType("arq.connections")
arq_cron = types.ModuleType("arq.cron")
arq_connections.RedisSettings = type("RedisSettings", (), {"__init__": lambda self, **kwargs: None})
arq_connections.create_pool = lambda *args, **kwargs: None
arq_cron.cron = lambda *args, **kwargs: (args, kwargs)
arq_module.connections = arq_connections
arq_module.cron = arq_cron
sys.modules.setdefault("arq", arq_module)
sys.modules.setdefault("arq.connections", arq_connections)
sys.modules.setdefault("arq.cron", arq_cron)
