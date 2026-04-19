# =================================================================
# FILE: file_upload.py
# =================================================================
# SCOPO: Gestione upload e storage file (documenti identità, CV)
#
# Features:
# - Upload sicuro con validazione tipo file
# - Storage organizzato per collaboratore
# - Generazione nomi file univoci
# - Gestione dimensione massima file
# - Sanitizzazione nomi file
# - Prevenzione nomi riservati Windows (nul, con, prn, aux, etc.)
# =================================================================

import os
import uuid
import shutil
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime
from fastapi import UploadFile, HTTPException
import logging

# Importa validatore per nomi riservati Windows.
# Compatibile sia con esecuzione da package sia con working dir /app.
try:
    from backend.windows_filename_validator import (
        sanitize_filename as windows_sanitize_filename,
        is_valid_filename as is_valid_windows_filename,
        is_windows_reserved_name,
        validate_and_fix_filename
    )
except ModuleNotFoundError:
    from windows_filename_validator import (
        sanitize_filename as windows_sanitize_filename,
        is_valid_filename as is_valid_windows_filename,
        is_windows_reserved_name,
        validate_and_fix_filename
    )

logger = logging.getLogger(__name__)

# =================================================================
# CONFIGURAZIONE
# =================================================================

# Directory base per storage files
UPLOAD_DIR = Path("uploads")
DOCUMENTS_DIR = UPLOAD_DIR / "documents"
CURRICULUM_DIR = UPLOAD_DIR / "curriculum"
ENTITY_LOGOS_DIR = UPLOAD_DIR / "entity_logos"

# Dimensione massima file: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes

# Estensioni permesse
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_CV_EXTENSIONS = {".pdf", ".doc", ".docx"}
ALLOWED_ENTITY_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".gif"}

# =================================================================
# SETUP DIRECTORIES
# =================================================================

def setup_upload_directories():
    """Crea directories per upload se non esistono"""
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    CURRICULUM_DIR.mkdir(parents=True, exist_ok=True)
    ENTITY_LOGOS_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Upload directories ready: {UPLOAD_DIR}")

# Crea directories all'import
setup_upload_directories()


# =================================================================
# VALIDAZIONE FILE
# =================================================================

def validate_file_extension(filename: str, allowed_extensions: set) -> bool:
    """
    Valida estensione file.

    Args:
        filename: Nome file
        allowed_extensions: Set di estensioni permesse (es. {'.pdf', '.jpg'})

    Returns:
        True se valido, False altrimenti
    """
    ext = Path(filename).suffix.lower()
    return ext in allowed_extensions


def sanitize_filename(filename: str) -> str:
    """
    Sanitizza nome file per sicurezza.

    Rimuove caratteri pericolosi e path traversal attacks.
    Previene l'uso di nomi problematici come "null", "None", "undefined".
    Previene nomi riservati Windows (nul, con, prn, aux, com1-9, lpt1-9).

    Args:
        filename: Nome file originale

    Returns:
        Nome file sanitizzato e sicuro per Windows/OneDrive

    Examples:
        >>> sanitize_filename("documento.pdf")
        "documento.pdf"
        >>> sanitize_filename("nul.txt")
        "file_unnamed.txt"
        >>> sanitize_filename("null.txt")
        "file_unnamed.txt"
    """
    # Usa il validatore Windows che include tutti i controlli
    # (null, None, undefined + nomi riservati Windows + caratteri invalidi)
    sanitized = windows_sanitize_filename(
        filename,
        default="file_unnamed",
        add_timestamp=False
    )

    # Prendi solo basename per sicurezza (previene path traversal)
    sanitized = os.path.basename(sanitized)

    # Verifica finale che il nome sia valido
    if not is_valid_windows_filename(sanitized):
        logger.warning(f"Nome file '{filename}' ancora invalido dopo sanitizzazione, uso default")
        return "file_unnamed"

    return sanitized


def generate_unique_filename(original_filename: str) -> str:
    """
    Genera nome file univoco mantenendo estensione originale.

    Args:
        original_filename: Nome file originale

    Returns:
        Nome file univoco: {uuid}_{timestamp}_{original_name}
    """
    # Sanitizza nome originale
    safe_name = sanitize_filename(original_filename)

    # Estrai estensione
    ext = Path(safe_name).suffix

    # Nome base senza estensione
    name_without_ext = Path(safe_name).stem

    # Genera nome univoco
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]  # Primi 8 caratteri UUID

    # Formato: uuid_timestamp_originale.ext
    unique_filename = f"{unique_id}_{timestamp}_{name_without_ext}{ext}"

    return unique_filename


# =================================================================
# UPLOAD FILE
# =================================================================

async def save_uploaded_file(
    file: UploadFile,
    collaborator_id: int,
    file_type: str  # "documento", "curriculum" o "logo_ente"
) -> Tuple[str, str]:
    """
    Salva file uploadato su filesystem.

    Args:
        file: File uploadato da FastAPI
        collaborator_id: ID collaboratore
        file_type: Tipo file ("documento", "curriculum" o "logo_ente")

    Returns:
        Tuple (filename, filepath)

    Raises:
        HTTPException: Se validazione fallisce
    """
    # Valida collaborator_id
    if not collaborator_id or str(collaborator_id) in ('null', 'None', 'undefined'):
        raise HTTPException(status_code=400, detail="ID collaboratore non valido")

    # Valida tipo file
    if file_type == "documento":
        target_dir = DOCUMENTS_DIR
        allowed_extensions = ALLOWED_DOCUMENT_EXTENSIONS
    elif file_type == "curriculum":
        target_dir = CURRICULUM_DIR
        allowed_extensions = ALLOWED_CV_EXTENSIONS
    elif file_type == "logo_ente":
        target_dir = ENTITY_LOGOS_DIR
        allowed_extensions = ALLOWED_ENTITY_LOGO_EXTENSIONS
    else:
        raise HTTPException(status_code=400, detail="Tipo file non valido")

    # Valida estensione
    if not validate_file_extension(file.filename, allowed_extensions):
        raise HTTPException(
            status_code=400,
            detail=f"Estensione file non permessa. Permesse: {', '.join(allowed_extensions)}"
        )

    # Genera nome file univoco
    unique_filename = generate_unique_filename(file.filename)

    # Crea subdirectory dedicata. Per i loghi usiamo l'ID ente, per gli altri l'ID collaboratore.
    owner_prefix = "entity" if file_type == "logo_ente" else "collaborator"
    owner_dir = target_dir / f"{owner_prefix}_{int(collaborator_id)}"
    owner_dir.mkdir(parents=True, exist_ok=True)

    # Path completo file
    file_path = owner_dir / unique_filename

    # Leggi e salva file con validazione dimensione
    try:
        # Leggi contenuto
        contents = await file.read()

        # Valida dimensione
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File troppo grande. Massimo: {MAX_FILE_SIZE / 1024 / 1024:.1f}MB"
            )

        # Scrivi file
        with open(file_path, "wb") as f:
            f.write(contents)

        logger.info(f"File saved: {file_path}")

        # Ritorna nome originale e path relativo
        relative_path = str(file_path.relative_to(UPLOAD_DIR))
        return file.filename, relative_path

    except Exception as e:
        logger.error(f"Error saving file: {e}")
        raise HTTPException(status_code=500, detail=f"Errore salvataggio file: {str(e)}")


async def delete_file(filepath: str) -> bool:
    """
    Elimina file da filesystem.

    Args:
        filepath: Path relativo file (da database)

    Returns:
        True se eliminato, False se non trovato
    """
    try:
        full_path = _normalize_stored_path(filepath)
        if full_path.exists():
            full_path.unlink()
            logger.info(f"File deleted: {full_path}")
            return True
        else:
            logger.warning(f"File not found: {full_path}")
            return False
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        return False


def get_file_path(relative_path: str) -> Path:
    """
    Ottieni path assoluto file da path relativo.

    Args:
        relative_path: Path relativo salvato in database

    Returns:
        Path assoluto file

    Raises:
        HTTPException: Se file non esiste
    """
    full_path = _normalize_stored_path(relative_path)

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File non trovato")

    # Security check: verifica che file sia dentro UPLOAD_DIR
    # Previene path traversal attacks
    try:
        full_path.resolve().relative_to(UPLOAD_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Accesso negato")

    return full_path


def _normalize_stored_path(stored_path: str) -> Path:
    """
    Normalizza i path salvati nel DB.

    Compatibilita':
    - upload storici/app: `documents/...`, `curriculum/...`
    - allegati email: `uploads/email_inbox/...`
    """
    candidate = Path(stored_path)
    if candidate.is_absolute():
        return candidate

    parts = candidate.parts
    if parts and parts[0] == UPLOAD_DIR.name:
        return candidate
    return UPLOAD_DIR / candidate


# =================================================================
# UTILITY
# =================================================================

def validate_name_not_null(name: str, default: str = "unnamed") -> str:
    """
    Valida che un nome (file, cartella, etc.) non sia null/None/undefined.

    Questa funzione previene problemi di sincronizzazione con OneDrive
    causati da file o cartelle con nome "null".

    Args:
        name: Nome da validare
        default: Nome di default da usare se il nome è invalido

    Returns:
        Nome valido (o default se il nome è invalido)

    Examples:
        >>> validate_name_not_null("documento.pdf")
        "documento.pdf"
        >>> validate_name_not_null(None)
        "unnamed"
        >>> validate_name_not_null("null")
        "unnamed"
    """
    # Lista di valori non permessi
    invalid_names = {'null', 'None', 'undefined', 'NULL', 'NONE', 'UNDEFINED', ''}

    # Converti in stringa e controlla
    name_str = str(name) if name is not None else ''

    # Se il nome è invalido o vuoto, usa il default
    if not name_str or name_str in invalid_names:
        logger.warning(f"Nome invalido rilevato: '{name}', uso '{default}'")
        return default

    return name_str


def get_file_info(filepath: str) -> dict:
    """
    Ottieni informazioni su file.

    Args:
        filepath: Path relativo file

    Returns:
        Dict con info file (size, created, modified)
    """
    try:
        full_path = UPLOAD_DIR / filepath
        if not full_path.exists():
            return None

        stat = full_path.stat()

        return {
            "filename": full_path.name,
            "size_bytes": stat.st_size,
            "size_mb": round(stat.st_size / 1024 / 1024, 2),
            "created_at": datetime.fromtimestamp(stat.st_ctime),
            "modified_at": datetime.fromtimestamp(stat.st_mtime)
        }
    except Exception as e:
        logger.error(f"Error getting file info: {e}")
        return None
