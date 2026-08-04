from types import SimpleNamespace

from backup_manager import BackupManager


def test_postgres_restore_uses_maintenance_database(monkeypatch, tmp_path):
    """Un dump --clean --create non puo' eliminare il DB a cui psql e' connesso."""
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://deploy_user:secret@db:5432/gestionale",
    )
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("backup_manager.subprocess.run", fake_run)
    manager = BackupManager(
        "postgresql+psycopg://deploy_user:secret@db:5432/gestionale",
        str(tmp_path),
    )

    manager._restore_postgresql(str(tmp_path / "backup.sql"))

    command, kwargs = calls[0]
    assert "--dbname=postgres" in command
    assert "--dbname=gestionale" not in command
    assert kwargs["env"]["PGPASSWORD"] == "secret"
