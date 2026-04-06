import argparse
import logging
import signal
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*args, **kwargs) -> bool:
        return False


CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR = CURRENT_FILE.parent.parent
PROJECT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import inspect

from database import SessionLocal, engine
import crud
import models
from services.email_sender import EmailSender


LOGGER = logging.getLogger("check_scadenze")
RUNNING = True


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def load_environment() -> None:
    load_dotenv(PROJECT_DIR / ".env", override=False)
    load_dotenv(BACKEND_DIR / ".env", override=False)


def handle_signal(signum, frame) -> None:
    del frame
    global RUNNING
    LOGGER.info("Ricevuto segnale %s, arresto scheduler check_scadenze...", signum)
    RUNNING = False


def _format_deadline(value: Optional[datetime]) -> str:
    if not value:
        return "Nessuna scadenza"
    return value.strftime("%d/%m/%Y")


def _build_notification_message(documento) -> tuple[str, str]:
    collaborator_name = getattr(documento.collaboratore, "full_name", None) or f"Collaboratore #{documento.collaboratore_id}"
    title = f"Documento in scadenza: {documento.tipo_documento}"
    message = (
        f"Il documento '{documento.tipo_documento}' di {collaborator_name} "
        f"scade il {_format_deadline(documento.data_scadenza)}."
    )
    return title, message


def ensure_required_tables() -> None:
    inspector = inspect(engine)
    if "notifiche" in inspector.get_table_names():
        return
    try:
        models.Notifica.__table__.create(bind=engine, checkfirst=True)
        LOGGER.info("Tabella notifiche creata automaticamente")
    except Exception as exc:
        LOGGER.warning("Impossibile creare automaticamente la tabella notifiche: %s", exc)


def _notification_exists(db, documento) -> bool:
    return db.query(models.Notifica).filter(
        models.Notifica.tipo == "documento_scadenza",
        models.Notifica.destinatario_id == documento.collaboratore_id,
        models.Notifica.riferimento_tipo == "documento",
        models.Notifica.riferimento_id == documento.id,
        models.Notifica.letta.is_(False),
    ).first() is not None


def _create_notification_for_document(db, documento, email_sender: EmailSender, send_email: bool) -> bool:
    if _notification_exists(db, documento):
        LOGGER.info("Notifica già presente per documento %s", documento.id)
        return False

    title, message = _build_notification_message(documento)
    notifica = models.Notifica(
        tipo="documento_scadenza",
        titolo=title,
        messaggio=message,
        destinatario_id=documento.collaboratore_id,
        destinatario_email=getattr(documento.collaboratore, "email", None),
        letta=False,
        inviata_email=False,
        riferimento_tipo="documento",
        riferimento_id=documento.id,
    )
    db.add(notifica)
    db.flush()
    LOGGER.info("Creata notifica %s per documento %s", notifica.id, documento.id)

    if send_email and notifica.destinatario_email:
        context = {
            "subject": title,
            "collaboratore_nome": getattr(documento.collaboratore, "full_name", "Collaboratore"),
            "documenti": [
                {
                    "nome": documento.tipo_documento,
                    "scadenza": _format_deadline(documento.data_scadenza),
                }
            ],
            "link_upload": f"https://placeholder.local/documenti/upload/{documento.id}",
        }
        sent = email_sender.send_template_email(
            to=notifica.destinatario_email,
            template_name="sollecito_documento",
            context=context,
        )
        notifica.inviata_email = sent
        notifica.data_invio_email = datetime.now() if sent else None
        LOGGER.info(
            "Invio email %s per notifica %s verso %s",
            "riuscito" if sent else "fallito",
            notifica.id,
            notifica.destinatario_email,
        )

    return True


def run_check(giorni: int = 7, send_email: bool = False) -> int:
    db = SessionLocal()
    email_sender = EmailSender()
    try:
        LOGGER.info("Avvio check scadenze documenti")
        scaduti = crud.marca_scaduti(db)
        LOGGER.info("Documenti marcati come scaduti: %s", len(scaduti))

        documenti = crud.get_documenti_in_scadenza(db, giorni=giorni)
        LOGGER.info("Documenti in scadenza entro %s giorni: %s", giorni, len(documenti))

        created_notifications = 0
        for documento in documenti:
            if _create_notification_for_document(db, documento, email_sender, send_email):
                created_notifications += 1

        db.commit()
        LOGGER.info("Check completato: notifiche create %s", created_notifications)
        return 0
    except Exception as exc:
        db.rollback()
        LOGGER.exception("Errore durante il check scadenze: %s", exc)
        return 1
    finally:
        db.close()


def command_schedule(run_at: str, giorni: int, send_email: bool) -> int:
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    LOGGER.info("Scheduler check scadenze attivo, esecuzione giornaliera alle %s", run_at)
    while RUNNING:
        now = datetime.now()
        target = datetime.strptime(run_at, "%H:%M").replace(
            year=now.year,
            month=now.month,
            day=now.day,
        )
        if target <= now:
            target = target.replace(day=now.day) + timedelta(days=1)

        wait_seconds = max((target - now).total_seconds(), 1)
        LOGGER.info("Prossima esecuzione pianificata alle %s", target.isoformat())
        slept = 0.0
        while RUNNING and slept < wait_seconds:
            chunk = min(30.0, wait_seconds - slept)
            time.sleep(chunk)
            slept += chunk

        if not RUNNING:
            break

        run_check(giorni=giorni, send_email=send_email)

    LOGGER.info("Scheduler check scadenze arrestato")
    return 0


def main() -> int:
    configure_logging()
    load_environment()

    parser = argparse.ArgumentParser(description="Controllo documenti in scadenza e notifiche")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Esegue un controllo immediato")
    run_parser.add_argument("--giorni", type=int, default=7, help="Finestra giorni per documenti in scadenza")
    run_parser.add_argument("--send-email", action="store_true", help="Invia email oltre a creare notifiche")

    schedule_parser = subparsers.add_parser("schedule", help="Avvia scheduler giornaliero")
    schedule_parser.add_argument("--time", default="08:00", help="Orario giornaliero formato HH:MM")
    schedule_parser.add_argument("--giorni", type=int, default=7, help="Finestra giorni per documenti in scadenza")
    schedule_parser.add_argument("--send-email", action="store_true", help="Invia email oltre a creare notifiche")

    args = parser.parse_args()

    ensure_required_tables()

    if not args.command:
        return run_check()
    if args.command == "run":
        return run_check(giorni=args.giorni, send_email=args.send_email)
    if args.command == "schedule":
        return command_schedule(run_at=args.time, giorni=args.giorni, send_email=args.send_email)

    LOGGER.error("Comando non supportato")
    return 1


if __name__ == "__main__":
    sys.exit(main())
