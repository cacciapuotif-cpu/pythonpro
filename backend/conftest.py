"""
conftest.py — configurazione globale pytest per PythonPro backend.

Gestisce:
- Mock di servizi esterni (arq, SMTP, LLM, WhatsApp) durante i test
- Variabili d'ambiente minime per avviare l'app in modalità test
- Fixture condivise tra test_main.py e tests/
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock

# ---------------------------------------------------------------------------
# 1. ENV VAR MINIME — impostare PRIMA di qualsiasi import dell'app
#    In CI sono iniettate via env; localmente questo file fa da fallback.
# ---------------------------------------------------------------------------
_TEST_DEFAULTS = {
    "ENVIRONMENT": "test",
    "JWT_SECRET_KEY": "test_secret_key_for_pytest_only_not_production_32ch",
    "SECRET_KEY": "test_secret_key_for_pytest_only_not_production_32ch",
    "ADMIN_DEFAULT_PASSWORD": "Admin123!PytestLocal",
    "OPERATOR_DEFAULT_PASSWORD": "Oper123!PytestLocal",
    "CORS_ALLOWED_ORIGINS": "http://localhost:3000",
    "SMTP_HOST": "",
    "SMTP_USER": "",
    "SMTP_PASSWORD": "",
    "SMTP_TEST_MODE": "true",
    "ENABLE_WHATSAPP": "false",
    "AI_AGENT_LLM_PROVIDER": "none",
    "REDIS_HOST": "localhost",
    "REDIS_PORT": "6379",
    "REDIS_PASSWORD": "",
    "AUTO_BACKUP_ENABLED": "false",
}
for _key, _val in _TEST_DEFAULTS.items():
    os.environ.setdefault(_key, _val)

# ---------------------------------------------------------------------------
# 2. MOCK ARQ — sostituisce il modulo arq prima che venga importato da
#    qualsiasi modulo applicativo. Necessario quando arq non è installato
#    o quando si vuole evitare di avviare worker reali nei test.
# ---------------------------------------------------------------------------
if "arq" not in sys.modules:
    _arq_mock = MagicMock()
    _arq_mock.connections = MagicMock()
    _arq_mock.connections.RedisSettings = MagicMock()
    _arq_mock.cron = MagicMock()
    _arq_mock.worker = MagicMock()
    sys.modules["arq"] = _arq_mock
    sys.modules["arq.connections"] = _arq_mock.connections
    sys.modules["arq.cron"] = _arq_mock.cron
    sys.modules["arq.worker"] = _arq_mock.worker

# ---------------------------------------------------------------------------
# 3. MOCK REDIS — usa un fake in-memory per test che non richiedono Redis
#    reale. Se Redis è disponibile (CI con service container), viene usato
#    il client reale e questo mock viene ignorato.
# ---------------------------------------------------------------------------
try:
    import redis

    _r = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        password=os.getenv("REDIS_PASSWORD") or None,
        socket_connect_timeout=1,
    )
    _r.ping()
    # Redis reale raggiungibile — nessun mock necessario
except Exception:
    # Redis non disponibile — mock in-memory
    _redis_store: dict = {}

    class _FakeRedis:
        def get(self, key):
            return _redis_store.get(key)

        def set(self, key, val, ex=None):
            _redis_store[key] = val

        def setex(self, key, ttl, val):
            _redis_store[key] = val

        def exists(self, key):
            return key in _redis_store

        def delete(self, *keys):
            for k in keys:
                _redis_store.pop(k, None)

        def incr(self, key):
            _redis_store[key] = int(_redis_store.get(key, 0)) + 1
            return _redis_store[key]

        def expire(self, key, ttl):
            pass

        def ping(self):
            return True

        def pipeline(self):
            return self

        def execute(self):
            return []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    # Patch il modulo auth e cache prima che vengano importati dall'app
    import unittest.mock

    _fake_redis_instance = _FakeRedis()

    # Patch lazy: viene applicato quando auth.py accede al client
    _redis_module_mock = MagicMock()
    _redis_module_mock.Redis.return_value = _fake_redis_instance
    _redis_module_mock.RedisError = redis.RedisError if "redis" in sys.modules else Exception

    # Non sostituire l'intero modulo redis (romperebbe i test che testano
    # errori redis), ma assicurarsi che il client usato dall'app sia il fake.
    # Il patch viene fatto a livello di fixture quando necessario.


# ---------------------------------------------------------------------------
# 4. MOCK SMTP — nessuna email reale durante i test
# ---------------------------------------------------------------------------
import smtplib
import unittest.mock

_smtp_mock = MagicMock()
_smtp_mock.return_value.__enter__ = MagicMock(return_value=_smtp_mock.return_value)
_smtp_mock.return_value.__exit__ = MagicMock(return_value=False)
_smtp_mock.return_value.sendmail = MagicMock(return_value={})
_smtp_mock.return_value.ehlo = MagicMock()
_smtp_mock.return_value.starttls = MagicMock()
_smtp_mock.return_value.login = MagicMock()


# ---------------------------------------------------------------------------
# 5. FIXTURE GLOBALI
# ---------------------------------------------------------------------------
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="session")
def test_engine(tmp_path_factory):
    """Engine SQLite condiviso per l'intera sessione di test."""
    db_path = tmp_path_factory.mktemp("db") / "pytest_session.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    return engine


@pytest.fixture(scope="function")
def db_session(tmp_path):
    """Sessione DB isolata per ogni singolo test (SQLite in-memory)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    from database import Base
    import models  # noqa: F401 — registra tutti i modelli

    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture(scope="function")
def client(db_session):
    """TestClient FastAPI con DB SQLite isolato e servizi mockati."""
    from main import app
    from database import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with unittest.mock.patch("smtplib.SMTP", _smtp_mock):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def auth_headers(client):
    """Restituisce header Authorization per un utente admin di test."""
    # Tenta login con le credenziali di default test
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "Admin123!PytestLocal"},
    )
    if resp.status_code == 200:
        token = resp.json().get("access_token", "")
        return {"Authorization": f"Bearer {token}"}
    # Se login non disponibile (DB vuoto, utenti non bootstrap) ritorna vuoto
    return {}
