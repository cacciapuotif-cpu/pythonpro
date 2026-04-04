# Sistema di backup automatico per il gestionale
import os
import shutil
import sqlite3
import subprocess
import time
import logging
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pathlib import Path
import threading
import zipfile
import hashlib
from urllib.parse import urlparse, unquote

try:
    import schedule
except ImportError:  # pragma: no cover - disponibile nel runtime completo
    schedule = None

logger = logging.getLogger(__name__)


def _parse_postgres_url(db_url: str):
    parsed = urlparse(db_url)
    if not parsed.scheme.startswith("postgresql"):
        raise ValueError("DATABASE_URL non configurato per PostgreSQL")

    user = unquote(parsed.username) if parsed.username else None
    password = unquote(parsed.password) if parsed.password else None
    host = parsed.hostname or "localhost"
    port = str(parsed.port or 5432)
    database = parsed.path.lstrip("/")

    if not user or not database:
        raise ValueError("DATABASE_URL non contiene credenziali o database validi")

    return user, password, host, port, database

class BackupManager:
    """Gestione backup automatici del database e configurazioni"""

    def __init__(self, db_path: str, backup_dir: str = "./backups"):
        self.db_path = db_path
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        self.max_backups = int(os.getenv("BACKUP_RETENTION_COUNT", "30"))
        self.is_running = False
        self.backup_thread = None

    def create_backup(self, backup_type: str = "manual") -> Optional[str]:
        """Crea un backup del database"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"gestionale_backup_{backup_type}_{timestamp}.db"
            backup_path = self.backup_dir / backup_filename

            if "sqlite" in self.db_path.lower():
                # Backup SQLite
                with sqlite3.connect(self.db_path) as source:
                    with sqlite3.connect(str(backup_path)) as backup:
                        source.backup(backup)
            else:
                # Backup PostgreSQL
                backup_filename = f"gestionale_backup_{backup_type}_{timestamp}.sql"
                backup_path = self.backup_dir / backup_filename
                self._backup_postgresql(str(backup_path))

            # Comprimi il backup
            compressed_path = self._compress_backup(backup_path)

            # Calcola checksum per verifica integrità
            checksum = self._calculate_checksum(compressed_path)

            # Salva metadata
            self._save_backup_metadata(compressed_path, backup_type, checksum)

            logger.info(f"Backup creato: {compressed_path}")

            # Pulizia backup vecchi
            self._cleanup_old_backups()

            return str(compressed_path)

        except Exception as e:
            logger.error(f"Errore creazione backup: {e}")
            return None

    def _backup_postgresql(self, backup_path: str):
        """Backup specifico per PostgreSQL"""
        db_url = os.getenv("DATABASE_URL", "")
        user, password, host, port, database = _parse_postgres_url(db_url)

        # Esegui pg_dump
        cmd = [
            "pg_dump",
            f"--host={host}",
            f"--port={port}",
            f"--username={user}",
            f"--dbname={database}",
            "--no-password",
            "--clean",
            "--create",
            f"--file={backup_path}"
        ]

        env = os.environ.copy()
        env["PGPASSWORD"] = password

        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"pg_dump failed: {result.stderr}")

    def _compress_backup(self, backup_path: Path) -> Path:
        """Comprimi il backup"""
        compressed_path = backup_path.with_suffix(backup_path.suffix + '.zip')

        with zipfile.ZipFile(compressed_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(backup_path, backup_path.name)

        # Rimuovi file non compresso
        backup_path.unlink()

        return compressed_path

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calcola checksum MD5 del file"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _save_backup_metadata(self, backup_path: Path, backup_type: str, checksum: str):
        """Salva metadati del backup"""
        metadata = {
            "timestamp": datetime.now().isoformat(),
            "backup_type": backup_type,
            "file_size": backup_path.stat().st_size,
            "checksum": checksum,
            "db_path": self.db_path
        }

        metadata_path = backup_path.with_suffix('.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

    def _cleanup_old_backups(self):
        """Rimuovi backup vecchi mantenendo solo gli ultimi max_backups"""
        backup_files = list(self.backup_dir.glob("gestionale_backup_*.zip"))
        backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        # Mantieni i backup più recenti
        for old_backup in backup_files[self.max_backups:]:
            try:
                old_backup.unlink()
                # Rimuovi anche i metadati
                metadata_file = old_backup.with_suffix('.json')
                if metadata_file.exists():
                    metadata_file.unlink()
                logger.info(f"Rimosso backup vecchio: {old_backup}")
            except Exception as e:
                logger.error(f"Errore rimozione backup {old_backup}: {e}")

    def restore_backup(self, backup_path: str, verify_checksum: bool = True) -> bool:
        """Ripristina un backup"""
        try:
            backup_file = Path(backup_path)

            if not backup_file.exists():
                logger.error(f"File backup non trovato: {backup_path}")
                return False

            # Verifica checksum se richiesto
            if verify_checksum:
                metadata_file = backup_file.with_suffix('.json')
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)

                    current_checksum = self._calculate_checksum(backup_file)
                    if current_checksum != metadata['checksum']:
                        logger.error("Checksum backup non corrispondente - file corrotto")
                        return False

            # Crea backup del database corrente prima del ripristino
            current_backup = self.create_backup("pre_restore")
            if not current_backup:
                logger.error("Impossibile creare backup di sicurezza")
                return False

            # Estrai backup
            restore_dir = self.backup_dir / "restore_temp"
            restore_dir.mkdir(exist_ok=True)

            with zipfile.ZipFile(backup_file, 'r') as zipf:
                zipf.extractall(restore_dir)

            # Trova il file database estratto
            extracted_files = list(restore_dir.glob("*.db")) + list(restore_dir.glob("*.sql"))
            if not extracted_files:
                logger.error("Nessun file database trovato nel backup")
                return False

            extracted_file = extracted_files[0]

            # Ripristina database
            if extracted_file.suffix == '.db':
                # SQLite
                shutil.copy2(extracted_file, self.db_path)
            else:
                # PostgreSQL
                self._restore_postgresql(str(extracted_file))

            # Pulizia
            shutil.rmtree(restore_dir)

            logger.info(f"Backup ripristinato con successo: {backup_path}")
            return True

        except Exception as e:
            logger.error(f"Errore ripristino backup: {e}")
            return False

    def _restore_postgresql(self, sql_file: str):
        """Ripristino specifico per PostgreSQL"""
        db_url = os.getenv("DATABASE_URL", "")
        user, password, host, port, database = _parse_postgres_url(db_url)

        # Esegui psql per ripristinare
        cmd = [
            "psql",
            f"--host={host}",
            f"--port={port}",
            f"--username={user}",
            f"--dbname={database}",
            "--no-password",
            f"--file={sql_file}"
        ]

        env = os.environ.copy()
        env["PGPASSWORD"] = password

        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"psql restore failed: {result.stderr}")

    def list_backups(self) -> List[Dict]:
        """Lista tutti i backup disponibili"""
        backups = []

        for backup_file in self.backup_dir.glob("gestionale_backup_*.zip"):
            metadata_file = backup_file.with_suffix('.json')

            backup_info = {
                "filename": backup_file.name,
                "path": str(backup_file),
                "size": backup_file.stat().st_size,
                "created": datetime.fromtimestamp(backup_file.stat().st_mtime).isoformat()
            }

            # Aggiungi metadati se disponibili
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    backup_info.update(metadata)
                except Exception as e:
                    logger.warning(f"Errore lettura metadati {metadata_file}: {e}")

            backups.append(backup_info)

        # Ordina per data di creazione (più recenti primi)
        backups.sort(key=lambda x: x['created'], reverse=True)
        return backups

    def schedule_automatic_backups(self):
        """Avvia scheduling backup automatici"""
        if schedule is None:
            raise RuntimeError("La libreria 'schedule' non è installata")

        daily_time = os.getenv("BACKUP_DAILY_TIME", "02:00")
        weekly_time = os.getenv("BACKUP_WEEKLY_TIME", "03:00")
        monthly_days = int(os.getenv("BACKUP_MONTHLY_INTERVAL_DAYS", "30"))

        schedule.clear()
        schedule.every().day.at(daily_time).do(lambda: self.create_backup("daily"))
        schedule.every().sunday.at(weekly_time).do(lambda: self.create_backup("weekly"))
        schedule.every(monthly_days).days.do(lambda: self.create_backup("monthly"))

        self.is_running = True
        self.backup_thread = threading.Thread(target=self._backup_scheduler, daemon=True)
        self.backup_thread.start()

        logger.info("Backup automatici avviati")

    def _backup_scheduler(self):
        """Thread per eseguire backup schedulati"""
        if schedule is None:
            raise RuntimeError("La libreria 'schedule' non è installata")
        while self.is_running:
            schedule.run_pending()
            time.sleep(60)  # Controlla ogni minuto

    def stop_automatic_backups(self):
        """Ferma backup automatici"""
        self.is_running = False
        if self.backup_thread:
            self.backup_thread.join(timeout=5)
        logger.info("Backup automatici fermati")

    def verify_backup_integrity(self, backup_path: str) -> bool:
        """Verifica integrità di un backup"""
        try:
            backup_file = Path(backup_path)
            metadata_file = backup_file.with_suffix('.json')

            # Verifica esistenza file
            if not backup_file.exists():
                logger.error(f"File backup non trovato: {backup_path}")
                return False

            # Verifica checksum se disponibile
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)

                current_checksum = self._calculate_checksum(backup_file)
                if current_checksum != metadata['checksum']:
                    logger.error(f"Checksum non corrispondente per {backup_path}")
                    return False

            # Verifica che il ZIP sia valido
            with zipfile.ZipFile(backup_file, 'r') as zipf:
                if zipf.testzip() is not None:
                    logger.error(f"File ZIP corrotto: {backup_path}")
                    return False

            logger.info(f"Backup integro: {backup_path}")
            return True

        except Exception as e:
            logger.error(f"Errore verifica integrità {backup_path}: {e}")
            return False

    def get_backup_statistics(self) -> Dict:
        """Ottieni statistiche sui backup"""
        backups = self.list_backups()

        if not backups:
            return {"total_backups": 0, "total_size": 0}

        total_size = sum(b['size'] for b in backups)
        backup_types = {}

        for backup in backups:
            backup_type = backup.get('backup_type', 'unknown')
            backup_types[backup_type] = backup_types.get(backup_type, 0) + 1

        return {
            "total_backups": len(backups),
            "total_size": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "backup_types": backup_types,
            "oldest_backup": backups[-1]['created'] if backups else None,
            "newest_backup": backups[0]['created'] if backups else None,
            "backup_directory": str(self.backup_dir)
        }

# Singleton per gestione backup globale
backup_manager = None

def get_backup_manager(db_path: str = None) -> BackupManager:
    """Ottieni istanza singleton del backup manager"""
    global backup_manager

    if backup_manager is None:
        if db_path is None:
            db_path = os.getenv("DATABASE_URL", "sqlite:///./gestionale_new.db")
            if db_path.startswith("sqlite:///"):
                db_path = db_path[10:]  # Rimuovi prefisso sqlite:///
        backup_dir = os.getenv("BACKUP_DIR", "./backups")
        backup_manager = BackupManager(db_path, backup_dir)

    return backup_manager
