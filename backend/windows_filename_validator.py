# =================================================================
# FILE: windows_filename_validator.py
# =================================================================
# SCOPO: Validazione e sanitizzazione nomi file per compatibilità Windows
#
# Previene l'uso di nomi riservati Windows (nul, con, prn, aux, com1-9, lpt1-9)
# e caratteri non permessi che causano problemi con OneDrive.
#
# Features:
# - Rilevamento nomi riservati Windows
# - Sanitizzazione automatica con fallback sicuri
# - Supporto per path completi
# - Logging per debugging
# - Generazione nomi univoci sicuri
# =================================================================

import re
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Union

logger = logging.getLogger(__name__)

# =================================================================
# CONFIGURAZIONE
# =================================================================

# Nomi riservati Windows (case-insensitive)
# Fonte: https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file
WINDOWS_RESERVED_NAMES = {
    'con', 'prn', 'aux', 'nul',
    'com1', 'com2', 'com3', 'com4', 'com5', 'com6', 'com7', 'com8', 'com9',
    'lpt1', 'lpt2', 'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9'
}

# Caratteri non permessi nei nomi file Windows
# < > : " / \ | ? *
WINDOWS_INVALID_CHARS = '<>:"|?*'

# Caratteri non permessi nei path Windows (più restrittivi)
WINDOWS_INVALID_PATH_CHARS = '<>"|?*'

# Nomi problematici aggiuntivi per OneDrive
# Includono anche "null", "None", "undefined"
ONEDRIVE_PROBLEMATIC_NAMES = {
    'null', 'none', 'undefined', 'NULL', 'NONE', 'UNDEFINED', 'None', 'Null'
}

# Set combinato di tutti i nomi da evitare
ALL_RESERVED_NAMES = WINDOWS_RESERVED_NAMES | ONEDRIVE_PROBLEMATIC_NAMES


# =================================================================
# FUNZIONI DI VALIDAZIONE
# =================================================================

def is_windows_reserved_name(name: str) -> bool:
    """
    Verifica se un nome è riservato in Windows.

    Args:
        name: Nome file/cartella da verificare (senza path)

    Returns:
        True se è un nome riservato, False altrimenti

    Examples:
        >>> is_windows_reserved_name("nul")
        True
        >>> is_windows_reserved_name("nul.txt")
        True
        >>> is_windows_reserved_name("con")
        True
        >>> is_windows_reserved_name("documento.pdf")
        False
    """
    if not name:
        return False

    # Estrai il nome base senza estensione
    base_name = Path(name).stem.lower()

    # Controlla se il nome (senza estensione) è riservato
    return base_name in ALL_RESERVED_NAMES


def contains_reserved_name(name: str) -> bool:
    """
    Verifica se un nome contiene nomi riservati come parte del nome.

    Più permissivo di is_windows_reserved_name() - cerca nomi riservati
    anche come parte del nome completo.

    Args:
        name: Nome da verificare

    Returns:
        True se contiene nomi riservati

    Examples:
        >>> contains_reserved_name("nul")
        True
        >>> contains_reserved_name("file_nul.txt")
        True
        >>> contains_reserved_name("nul_data")
        True
        >>> contains_reserved_name("manual.txt")
        False
    """
    if not name:
        return False

    name_lower = name.lower()

    # Rimuovi estensione per controllo
    base_name = Path(name).stem.lower()

    for reserved in ALL_RESERVED_NAMES:
        # Controllo esatto
        if base_name == reserved:
            return True

        # Controllo come parte del nome con separatori
        # Es: "nul_file", "file_nul", "nul-data"
        pattern = f"(^|_|-){reserved}(_|-|$)"
        if re.search(pattern, base_name):
            return True

    return False


def has_invalid_chars(name: str, check_path: bool = False) -> bool:
    """
    Verifica se un nome contiene caratteri non permessi in Windows.

    Args:
        name: Nome da verificare
        check_path: Se True, usa caratteri invalidi per path (meno restrittivi)

    Returns:
        True se contiene caratteri invalidi

    Examples:
        >>> has_invalid_chars("file<test>.txt")
        True
        >>> has_invalid_chars("file:test.txt")
        True
        >>> has_invalid_chars("documento.pdf")
        False
    """
    if not name:
        return False

    invalid_chars = WINDOWS_INVALID_PATH_CHARS if check_path else WINDOWS_INVALID_CHARS

    return any(char in name for char in invalid_chars)


def is_valid_filename(name: str) -> bool:
    """
    Verifica se un nome è valido per Windows e OneDrive.

    Controlla:
    - Non è vuoto o None
    - Non è un nome riservato Windows
    - Non contiene nomi riservati
    - Non contiene caratteri invalidi
    - Non inizia o finisce con spazio o punto

    Args:
        name: Nome da validare

    Returns:
        True se il nome è valido

    Examples:
        >>> is_valid_filename("documento.pdf")
        True
        >>> is_valid_filename("nul")
        False
        >>> is_valid_filename("")
        False
        >>> is_valid_filename(".hidden")
        False (inizia con punto)
    """
    if not name or not name.strip():
        return False

    # Controlla nomi riservati
    if is_windows_reserved_name(name) or contains_reserved_name(name):
        return False

    # Controlla caratteri invalidi
    if has_invalid_chars(name):
        return False

    # Non deve iniziare o finire con spazio
    if name != name.strip():
        return False

    # Non deve finire con punto o spazio (Windows)
    if name.endswith('.') or name.endswith(' '):
        return False

    return True


# =================================================================
# FUNZIONI DI SANITIZZAZIONE
# =================================================================

def sanitize_filename(
    filename: str,
    default: str = "file_unnamed",
    add_timestamp: bool = False
) -> str:
    """
    Sanitizza un nome file per renderlo sicuro per Windows/OneDrive.

    Args:
        filename: Nome file da sanitizzare
        default: Nome di default se il filename è invalido
        add_timestamp: Se True, aggiunge timestamp per unicità

    Returns:
        Nome file sanitizzato

    Examples:
        >>> sanitize_filename("nul.txt")
        "file_unnamed.txt"
        >>> sanitize_filename("documento<test>.pdf")
        "documento_test_.pdf"
        >>> sanitize_filename("null")
        "file_unnamed"
    """
    if not filename or not filename.strip():
        logger.warning(f"Nome file vuoto, uso default: {default}")
        return default

    # Estrai estensione
    path_obj = Path(filename)
    stem = path_obj.stem
    suffix = path_obj.suffix

    # Controlla se il nome (senza estensione) è riservato
    if stem.lower() in ALL_RESERVED_NAMES:
        logger.warning(f"Nome file riservato '{stem}', uso default: {default}")
        stem = Path(default).stem

    # Rimuovi caratteri invalidi (sostituisci con underscore)
    for char in WINDOWS_INVALID_CHARS:
        stem = stem.replace(char, '_')

    # Rimuovi spazi iniziali/finali
    stem = stem.strip()

    # Rimuovi punti finali
    stem = stem.rstrip('.')

    # Se il nome è diventato vuoto, usa default
    if not stem:
        logger.warning(f"Nome file vuoto dopo sanitizzazione, uso default: {default}")
        stem = Path(default).stem

    # Verifica ancora che non sia un nome riservato dopo sanitizzazione
    if stem.lower() in ALL_RESERVED_NAMES:
        stem = f"safe_{stem}"

    # Aggiungi timestamp se richiesto
    if add_timestamp:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        stem = f"{stem}_{timestamp}"

    # Ricomponi nome con estensione
    sanitized = f"{stem}{suffix}"

    if sanitized != filename:
        logger.info(f"Nome file sanitizzato: '{filename}' -> '{sanitized}'")

    return sanitized


def sanitize_path(
    filepath: Union[str, Path],
    default_name: str = "file_unnamed"
) -> Path:
    """
    Sanitizza un path completo, inclusi tutti i segmenti.

    Args:
        filepath: Path da sanitizzare
        default_name: Nome di default per segmenti invalidi

    Returns:
        Path sanitizzato

    Examples:
        >>> sanitize_path("uploads/nul/file.pdf")
        Path("uploads/dir_renamed/file.pdf")
        >>> sanitize_path("C:/docs/con/test.txt")
        Path("C:/docs/dir_renamed/test.txt")
    """
    path_obj = Path(filepath)

    # Sanitizza ogni segmento del path
    sanitized_parts = []

    for part in path_obj.parts:
        # Salta parti speciali (drive letters, /, \\)
        if part in ('/', '\\') or (len(part) == 2 and part[1] == ':'):
            sanitized_parts.append(part)
            continue

        # Sanitizza il segmento
        if is_windows_reserved_name(part) or contains_reserved_name(part):
            # Per directory, usa un nome generico
            safe_part = "dir_renamed"
            logger.warning(f"Segmento path riservato '{part}', uso '{safe_part}'")
            sanitized_parts.append(safe_part)
        else:
            # Sanitizza caratteri
            safe_part = part
            for char in WINDOWS_INVALID_PATH_CHARS:
                safe_part = safe_part.replace(char, '_')
            sanitized_parts.append(safe_part)

    # Ricostruisci path
    sanitized_path = Path(*sanitized_parts)

    if sanitized_path != path_obj:
        logger.info(f"Path sanitizzato: '{filepath}' -> '{sanitized_path}'")

    return sanitized_path


def generate_safe_filename(
    base_name: str = "file",
    extension: str = "",
    add_uuid: bool = False
) -> str:
    """
    Genera un nome file sicuro e univoco.

    Args:
        base_name: Nome base
        extension: Estensione (con o senza punto)
        add_uuid: Se True, aggiunge UUID per maggiore unicità

    Returns:
        Nome file sicuro e univoco

    Examples:
        >>> generate_safe_filename("document", "pdf")
        "document_20250106_143022.pdf"
        >>> generate_safe_filename("data", ".csv", add_uuid=True)
        "data_20250106_143022_a1b2c3d4.csv"
    """
    import uuid

    # Sanitizza base_name
    safe_base = sanitize_filename(base_name, default="file")
    safe_base = Path(safe_base).stem  # Rimuovi eventuale estensione

    # Timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # UUID opzionale
    uuid_part = ""
    if add_uuid:
        uuid_part = f"_{str(uuid.uuid4())[:8]}"

    # Assicurati che l'estensione inizi con punto
    if extension and not extension.startswith('.'):
        extension = f".{extension}"

    return f"{safe_base}_{timestamp}{uuid_part}{extension}"


# =================================================================
# UTILITY
# =================================================================

def validate_and_fix_filename(
    filename: str,
    default: str = "file_unnamed",
    raise_on_invalid: bool = False
) -> str:
    """
    Valida un nome file e lo corregge se necessario.

    Args:
        filename: Nome file da validare
        default: Nome di default se invalido
        raise_on_invalid: Se True, solleva eccezione invece di correggere

    Returns:
        Nome file valido

    Raises:
        ValueError: Se raise_on_invalid=True e il nome è invalido

    Examples:
        >>> validate_and_fix_filename("documento.pdf")
        "documento.pdf"
        >>> validate_and_fix_filename("nul.txt")
        "file_unnamed.txt"
        >>> validate_and_fix_filename("nul.txt", raise_on_invalid=True)
        ValueError: Nome file invalido: 'nul.txt'
    """
    if is_valid_filename(filename):
        return filename

    if raise_on_invalid:
        raise ValueError(f"Nome file invalido: '{filename}'")

    # Correggi il nome
    return sanitize_filename(filename, default=default)


def get_safe_temp_filename(prefix: str = "temp", extension: str = "") -> str:
    """
    Genera un nome file temporaneo sicuro.

    Args:
        prefix: Prefisso del nome
        extension: Estensione file

    Returns:
        Nome file temporaneo sicuro

    Examples:
        >>> get_safe_temp_filename("upload", ".pdf")
        "temp_upload_20250106_143022_a1b2c3d4.pdf"
    """
    safe_prefix = sanitize_filename(prefix, default="temp")
    safe_prefix = Path(safe_prefix).stem

    return generate_safe_filename(
        base_name=f"temp_{safe_prefix}",
        extension=extension,
        add_uuid=True
    )


# =================================================================
# TEST SELF-CHECK
# =================================================================

def run_self_tests():
    """Esegue test di auto-verifica del modulo"""
    print("Esecuzione test di auto-verifica...")

    # Test nomi riservati
    assert is_windows_reserved_name("nul") == True
    assert is_windows_reserved_name("nul.txt") == True
    assert is_windows_reserved_name("con") == True
    assert is_windows_reserved_name("documento.pdf") == False

    # Test sanitizzazione
    assert sanitize_filename("nul.txt") == "file_unnamed.txt"
    assert sanitize_filename("null.txt") == "file_unnamed.txt"
    assert sanitize_filename("documento.pdf") == "documento.pdf"

    # Test validazione
    assert is_valid_filename("documento.pdf") == True
    assert is_valid_filename("nul") == False
    assert is_valid_filename("null") == False

    print("[OK] Tutti i test superati!")


if __name__ == "__main__":
    run_self_tests()
