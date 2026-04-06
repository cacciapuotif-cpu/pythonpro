"""
============================================================
⚙️ FILE: settings.py
------------------------------------------------------------
Questo modulo definisce tutte le impostazioni centrali del gestionale.
Usa Pydantic per leggere le variabili d'ambiente (.env) in modo sicuro.
Tutte le configurazioni passano da qui, per mantenere il codice ordinato
e coerente. Tutto il gestionale dipende da questo file.
============================================================
"""

from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache
from typing import List, Union

class Settings(BaseSettings):
    """
    Classe principale delle impostazioni.
    Tutti i parametri qui definiti possono essere letti da variabili
    d'ambiente (.env) o avranno un valore predefinito.
    Ogni campo ha un commento in italiano per spiegare il suo scopo.
    """

    # === Parametri generali dell'applicazione ===
    APP_NAME: str = "Gestionale Collaboratori e Progetti"
    APP_ENV: str = "development"  # valori possibili: development / production
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True  # se True, mostra log di debug e ricarica automatica

    # === Configurazione del server ===
    HOST: str = "0.0.0.0"   # host di ascolto
    PORT: int = 8000        # porta HTTP del server FastAPI

    # === Database ===
    DATABASE_URL: str = (
        "postgresql+asyncpg://gestionale:gestionale123@localhost:5432/gestionale"
    )
    # 👉 Nota: sostituire user/password con valori reali nel file .env
    # Il formato è: postgresql+asyncpg://<utente>:<password>@<host>:<porta>/<database>
    # Per sviluppo locale con SQLite: "sqlite:///./gestionale.db"

    # Parametri pool connessioni database
    DB_POOL_SIZE: int = 20           # numero connessioni mantenute aperte
    DB_MAX_OVERFLOW: int = 30        # numero massimo connessioni extra
    DB_POOL_TIMEOUT: int = 30        # timeout attesa connessione (secondi)
    DB_ECHO: bool = False            # se True, logga tutte le query SQL

    # === Sicurezza e JWT ===
    JWT_SECRET_KEY: str = "changeme-secret-key-super-sicura-da-sostituire"  # chiave segreta JWT (da .env)
    JWT_ALGORITHM: str = "HS256"  # algoritmo di firma
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # durata token di accesso (1 ora)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7     # durata token di refresh (7 giorni)

    # Password hashing
    PWD_HASH_ALGORITHM: str = "bcrypt"  # algoritmo hashing password
    PWD_SALT_ROUNDS: int = 12           # numero di round bcrypt (più alto = più sicuro ma più lento)

    # === CORS (Cross-Origin Resource Sharing) ===
    BACKEND_CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001"
    ]
    # Per maggiore sicurezza in produzione, specificare solo i domini autorizzati

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        """
        Validator per BACKEND_CORS_ORIGINS che accetta:
        - Lista di stringhe (default)
        - Stringa singola (convertita a lista)
        - Stringa con virgole separate (convertita a lista)
        - Stringa JSON (parsata e convertita a lista)
        """
        if isinstance(v, str):
            # Se è una stringa vuota, ritorna lista vuota
            if not v or v.strip() == "":
                return []
            # Prova a parsare come JSON
            try:
                import json
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
            # Se contiene virgole, splitta
            if "," in v:
                return [origin.strip() for origin in v.split(",") if origin.strip()]
            # Altrimenti, ritorna lista con un singolo elemento
            return [v]
        return v

    # === Logging ===
    LOG_LEVEL: str = "INFO"  # Livelli: DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    LOG_FILE: str = "logs/gestionale.log"  # path file log

    # === Email / SMTP ===
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str = "no-reply@gestionale.local"
    SMTP_TEST_MODE: bool = True
    SMTP_USE_TLS: bool = True

    # Alias legacy mantenuti per compatibilità
    SMTP_SERVER: str | None = None
    EMAIL_FROM: str = "no-reply@gestionale.local"
    ENABLE_EMAIL: bool = False  # Abilita invio email

    # === Upload file ===
    UPLOAD_DIR: str = "uploads"  # directory per file caricati
    MAX_UPLOAD_SIZE_MB: int = 10  # dimensione massima upload (MB)
    ALLOWED_UPLOAD_EXTENSIONS: List[str] = [
        ".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"
    ]

    # === Backup automatico ===
    ENABLE_AUTO_BACKUP: bool = False
    BACKUP_DIR: str = "backups"
    BACKUP_RETENTION_DAYS: int = 30  # giorni di retention backup

    # === Rate limiting ===
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60  # richieste max per minuto per IP

    # === Feature flags ===
    ENABLE_SWAGGER_DOCS: bool = True  # Abilita documentazione Swagger in /docs
    ENABLE_MONITORING: bool = True    # Abilita endpoint monitoraggio performance
    ENABLE_AUDIT_LOG: bool = True     # Abilita log audit per azioni critiche

    class Config:
        """
        Configurazione Pydantic per il caricamento delle impostazioni.
        """
        env_file = ".env"  # il file da cui leggere le variabili
        env_file_encoding = "utf-8"
        case_sensitive = True  # le variabili sono case-sensitive

@lru_cache()
def get_settings() -> Settings:
    """
    Restituisce un'istanza unica (cached) delle impostazioni.

    Questo evita di ricaricare i parametri più volte e migliora le performance.
    La decorazione @lru_cache() garantisce che venga creata una sola istanza
    durante tutto il ciclo di vita dell'applicazione.

    Returns:
        Settings: Istanza singleton delle impostazioni

    Esempio d'uso:
        ```python
        from backend.app.core.settings import get_settings

        settings = get_settings()
        print(settings.DATABASE_URL)
        print(settings.APP_NAME)
        ```
    """
    return Settings()


# ============================================================
# ESPORTAZIONI
# ============================================================
# Rende disponibili le funzioni/classi quando si importa il modulo
__all__ = ["Settings", "get_settings"]
