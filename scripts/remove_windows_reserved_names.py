#!/usr/bin/env python3
"""
Script per trovare ed eliminare file/cartelle con nomi riservati Windows.

I nomi riservati Windows (nul, con, prn, aux, com1-9, lpt1-9) causano problemi
di sincronizzazione con OneDrive e non possono essere usati come nomi di file.

Uso:
    python scripts/remove_windows_reserved_names.py              # Solo scansione
    python scripts/remove_windows_reserved_names.py --fix        # Rimuove i file
    python scripts/remove_windows_reserved_names.py --rename     # Rinomina invece di rimuovere
    python scripts/remove_windows_reserved_names.py --verbose    # Output dettagliato
"""

import os
import sys
import argparse
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Set, Tuple

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

# Directory da escludere dalla scansione
DEFAULT_EXCLUDES = {
    'node_modules',
    'venv',
    '.git',
    '__pycache__',
    '.pytest_cache',
    'dist',
    'build',
    '.next',
    '.venv',
    'env'
}

# =================================================================
# FUNZIONI UTILITY
# =================================================================

def is_windows_reserved_name(name: str) -> bool:
    """
    Verifica se un nome è riservato in Windows.

    Args:
        name: Nome file/cartella da verificare

    Returns:
        True se è un nome riservato, False altrimenti
    """
    # Estrai il nome base senza estensione
    base_name = Path(name).stem.lower()

    # Controlla se il nome completo (senza estensione) è riservato
    if base_name in WINDOWS_RESERVED_NAMES:
        return True

    # Controlla se il nome contiene parole riservate
    # Es: "nul_file.txt", "file_nul.txt", "nul", etc.
    name_parts = base_name.split('_')
    for part in name_parts:
        if part in WINDOWS_RESERVED_NAMES:
            return True

    return False


def contains_reserved_substring(name: str) -> bool:
    """
    Verifica se un nome contiene sottostringhe riservate.

    Più permissivo di is_windows_reserved_name() - cerca "nul" anche
    all'interno di nomi più lunghi.

    Args:
        name: Nome da verificare

    Returns:
        True se contiene sottostringhe riservate
    """
    name_lower = name.lower()

    # Cerca "nul" come parola intera o parte di nome
    # Es: "nul", "nul.txt", "file_nul.txt", "nul_data"
    for reserved in WINDOWS_RESERVED_NAMES:
        # Cerca esatta corrispondenza (case-insensitive)
        if name_lower == reserved:
            return True

        # Cerca con estensione (es: "nul.txt")
        if name_lower.startswith(f"{reserved}."):
            return True

        # Cerca come parte del nome con underscore
        if f"_{reserved}_" in name_lower or \
           f"_{reserved}." in name_lower or \
           name_lower.startswith(f"{reserved}_") or \
           f"_{reserved}" in name_lower and name_lower.endswith(reserved):
            return True

    return False


def generate_safe_name(original_path: Path) -> str:
    """
    Genera un nome sicuro per un file/directory problematico.

    Args:
        original_path: Path originale

    Returns:
        Nome sicuro da usare
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    suffix = original_path.suffix

    if original_path.is_file():
        return f"file_renamed_{timestamp}{suffix}"
    else:
        return f"dir_renamed_{timestamp}"


# =================================================================
# SCANNER
# =================================================================

class WindowsReservedNameScanner:
    """Scanner per trovare file/cartelle con nomi riservati Windows"""

    def __init__(self, root_dir: str = ".", excludes: Set[str] = None, verbose: bool = False):
        self.root_dir = Path(root_dir).resolve()
        self.excludes = excludes or DEFAULT_EXCLUDES
        self.problematic_paths: List[Path] = []
        self.verbose = verbose

    def should_exclude(self, path: Path) -> bool:
        """Verifica se il path deve essere escluso dalla scansione"""
        return any(exclude in path.parts for exclude in self.excludes)

    def scan(self) -> List[Path]:
        """
        Scansiona il progetto cercando nomi riservati Windows.

        Returns:
            Lista di Path con nomi problematici
        """
        print(f"[*] Scansionando {self.root_dir}...")
        print(f"    Escludendo: {', '.join(self.excludes)}\n")

        count = 0

        for root, dirs, files in os.walk(self.root_dir):
            root_path = Path(root)

            # Escludi directory
            if self.should_exclude(root_path):
                dirs.clear()  # Non scendere nelle sottodirectory
                continue

            # Controlla nomi directory
            for dir_name in dirs[:]:
                if contains_reserved_substring(dir_name):
                    problematic_path = root_path / dir_name
                    self.problematic_paths.append(problematic_path)
                    print(f"[X] [DIRECTORY] {problematic_path}")
                    count += 1

            # Controlla nomi file
            for file_name in files:
                if contains_reserved_substring(file_name):
                    problematic_path = root_path / file_name
                    self.problematic_paths.append(problematic_path)
                    print(f"[X] [FILE] {problematic_path}")
                    count += 1

            # Progress feedback ogni 100 directory
            if self.verbose and count > 0 and count % 100 == 0:
                print(f"   ... trovati {count} file problematici finora ...")

        return self.problematic_paths

    def remove(self, dry_run: bool = True) -> Tuple[int, int]:
        """
        Rimuove i file/directory problematici.

        Args:
            dry_run: Se True, mostra solo cosa verrebbe rimosso

        Returns:
            Tuple (successi, errori)
        """
        if not self.problematic_paths:
            print("\n[OK] Nessun file da rimuovere")
            return 0, 0

        print(f"\n{'[DRY RUN] ' if dry_run else ''}[DELETE] Rimozione {len(self.problematic_paths)} file/directory...")

        success_count = 0
        error_count = 0

        for path in self.problematic_paths:
            try:
                if dry_run:
                    print(f"   [SIMULA] Rimuoverei: {path}")
                    success_count += 1
                else:
                    if path.is_file():
                        path.unlink()
                        print(f"   [OK] Rimosso file: {path}")
                    elif path.is_dir():
                        shutil.rmtree(path)
                        print(f"   [OK] Rimossa directory: {path}")
                    success_count += 1
            except Exception as e:
                print(f"   [ERROR] Errore rimuovendo {path}: {e}")
                error_count += 1

        return success_count, error_count

    def rename(self, dry_run: bool = True) -> Tuple[int, int]:
        """
        Rinomina i file/directory problematici invece di rimuoverli.

        Args:
            dry_run: Se True, mostra solo cosa verrebbe rinominato

        Returns:
            Tuple (successi, errori)
        """
        if not self.problematic_paths:
            print("\n[OK] Nessun file da rinominare")
            return 0, 0

        print(f"\n{'[DRY RUN] ' if dry_run else ''}[RENAME] Rinominando {len(self.problematic_paths)} file/directory...")

        success_count = 0
        error_count = 0

        for old_path in self.problematic_paths:
            try:
                new_name = generate_safe_name(old_path)
                new_path = old_path.parent / new_name

                # Assicurati che il nuovo nome non esista già
                counter = 1
                while new_path.exists():
                    base = Path(new_name).stem
                    suffix = Path(new_name).suffix
                    new_name = f"{base}_{counter}{suffix}"
                    new_path = old_path.parent / new_name
                    counter += 1

                if dry_run:
                    print(f"   [SIMULA] {old_path.name} -> {new_name}")
                    success_count += 1
                else:
                    old_path.rename(new_path)
                    print(f"   [OK] {old_path.name} -> {new_name}")
                    success_count += 1

            except Exception as e:
                print(f"   [ERROR] Errore rinominando {old_path}: {e}")
                error_count += 1

        return success_count, error_count

    def report(self) -> None:
        """Stampa report dei risultati"""
        print("\n" + "="*70)
        print("REPORT - Nomi Riservati Windows")
        print("="*70)

        if not self.problematic_paths:
            print("[OK] SUCCESSO: Nessun file o directory con nome riservato Windows!")
            print("\nIl progetto e' conforme ai requisiti di OneDrive.")
        else:
            print(f"[WARN] ATTENZIONE: Trovati {len(self.problematic_paths)} file/directory problematici!")
            print("\nQuesti file causano problemi di sincronizzazione con OneDrive.")
            print("\nOpzioni:")
            print("  --fix     : Rimuove i file problematici")
            print("  --rename  : Rinomina i file invece di rimuoverli")

        print("="*70)


# =================================================================
# MAIN
# =================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Trova e rimuove file/directory con nomi riservati Windows",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--fix',
        action='store_true',
        help='Rimuove automaticamente file problematici (ATTENZIONE: permanente!)'
    )

    parser.add_argument(
        '--rename',
        action='store_true',
        help='Rinomina file problematici invece di rimuoverli (più sicuro)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Mostra cosa verrebbe fatto senza eseguire'
    )

    parser.add_argument(
        '--exclude',
        nargs='+',
        default=list(DEFAULT_EXCLUDES),
        help=f'Directory da escludere (default: {", ".join(DEFAULT_EXCLUDES)})'
    )

    parser.add_argument(
        '--root',
        default='.',
        help='Directory radice da scansionare (default: .)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Output dettagliato'
    )

    args = parser.parse_args()

    try:
        # Crea scanner
        scanner = WindowsReservedNameScanner(
            root_dir=args.root,
            excludes=set(args.exclude),
            verbose=args.verbose
        )

        # Scansiona
        problematic = scanner.scan()

        # Esegui azione richiesta
        if args.fix:
            if not args.dry_run:
                response = input("\n[WARN] ATTENZIONE: Stai per ELIMINARE i file. Continuare? (si/no): ")
                if response.lower() != 'si':
                    print("Operazione annullata.")
                    return 0

            success, errors = scanner.remove(dry_run=args.dry_run)
            print(f"\n[OK] Successi: {success}, [ERROR] Errori: {errors}")

        elif args.rename:
            success, errors = scanner.rename(dry_run=args.dry_run)
            print(f"\n[OK] Successi: {success}, [ERROR] Errori: {errors}")

        # Stampa report
        scanner.report()

        # Exit code
        return 1 if problematic else 0

    except KeyboardInterrupt:
        print("\n\n[WARN] Operazione interrotta dall'utente")
        return 2
    except Exception as e:
        print(f"\n[ERROR] Errore: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
