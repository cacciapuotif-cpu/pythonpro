import argparse
import logging
import signal
import sys
import time
from pathlib import Path

from backup_manager import get_backup_manager

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback per ambienti minimi
    def load_dotenv(*args, **kwargs) -> bool:
        return False


LOGGER = logging.getLogger("backup_cli")
RUNNING = True


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def load_environment() -> None:
    backend_dir = Path(__file__).resolve().parent
    project_dir = backend_dir.parent
    load_dotenv(project_dir / ".env", override=False)
    load_dotenv(backend_dir / ".env", override=False)


def handle_signal(signum, frame) -> None:
    del frame
    global RUNNING
    LOGGER.info("Ricevuto segnale %s, arresto scheduler backup...", signum)
    RUNNING = False


def command_create(backup_type: str) -> int:
    manager = get_backup_manager()
    backup_path = manager.create_backup(backup_type)
    if not backup_path:
        LOGGER.error("Creazione backup fallita")
        return 1

    LOGGER.info("Backup creato: %s", backup_path)
    return 0


def command_schedule() -> int:
    manager = get_backup_manager()
    manager.schedule_automatic_backups()
    LOGGER.info("Scheduler backup attivo")
    LOGGER.info("Directory backup: %s", manager.backup_dir)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    while RUNNING:
        time.sleep(1)

    manager.stop_automatic_backups()
    LOGGER.info("Scheduler backup arrestato")
    return 0


def main() -> int:
    configure_logging()
    load_environment()

    parser = argparse.ArgumentParser(description="Gestione backup PythonPro")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Crea un backup immediato")
    create_parser.add_argument("--type", default="manual", help="Tipo backup da registrare nei metadata")

    subparsers.add_parser("schedule", help="Avvia lo scheduler backup")
    subparsers.add_parser("list", help="Mostra l'elenco dei backup")

    args = parser.parse_args()

    if args.command == "create":
        return command_create(args.type)
    if args.command == "schedule":
        return command_schedule()
    if args.command == "list":
        manager = get_backup_manager()
        for backup in manager.list_backups():
            print(f"{backup['created']} {backup['filename']}")
        return 0

    LOGGER.error("Comando non supportato")
    return 1


if __name__ == "__main__":
    sys.exit(main())
