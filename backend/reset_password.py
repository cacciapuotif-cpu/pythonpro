import os
import secrets
from urllib.parse import urlparse

import bcrypt
import psycopg


def _database_url() -> str:
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("DATABASE_URL non configurata")
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


def reset_admin_password() -> tuple[int, str]:
    admin_email = os.getenv("RESET_ADMIN_EMAIL", "admin@gestionale.local")
    new_password = secrets.token_urlsafe(24)
    hashed = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    parsed = urlparse(_database_url())
    if not all([parsed.hostname, parsed.path, parsed.username, parsed.password]):
        raise RuntimeError("DATABASE_URL incompleta")

    with psycopg.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        dbname=parsed.path.lstrip("/"),
        user=parsed.username,
        password=parsed.password,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET hashed_password=%s WHERE email=%s RETURNING id",
                (hashed, admin_email),
            )
            row = cur.fetchone()
            if row is None:
                raise RuntimeError("utente admin non trovato")
        conn.commit()

    return int(row[0]), new_password


if __name__ == "__main__":
    user_id, password = reset_admin_password()
    print(f"OK: password monouso generata per user id={user_id}")
    print(f"PASSWORD_MONOUSO={password}")
