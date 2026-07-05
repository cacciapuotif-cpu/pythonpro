from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_reset_password_generates_one_time_password():
    text = (BACKEND_ROOT / "reset_password.py").read_text()
    assert "Admin2026!" not in text
    assert "password = \"" not in text
    assert "password = \'" not in text
    assert "secrets.token_urlsafe" in text
    assert "PASSWORD_MONOUSO=" in text


def test_validate_env_requires_backup_encryption_key():
    text = (BACKEND_ROOT / "scripts" / "validate_env.sh").read_text()
    assert 'require_nodefault "BACKUP_ENCRYPTION_KEY"' in text
