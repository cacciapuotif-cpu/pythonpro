#!/usr/bin/env python3
"""
Script AGGRESSIVO per rimuovere file/cartelle con "nul" nel nome.

ATTENZIONE: Questo script elimina automaticamente file problematici!
Protegge node_modules e venv (contengono librerie legittime).

Uso:
    python scripts/remove_nul_files_aggressive.py --scan      # Solo scansione
    python scripts/remove_nul_files_aggressive.py --fix       # Elimina file problematici
    python scripts/remove_nul_files_aggressive.py --fix-all   # Elimina TUTTO (anche node_modules!)
"""

import os
import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime

# =================================================================
# CONFIGURAZIONE
# =================================================================

# Directory da PROTEGGERE (non toccare mai)
PROTECTED_DIRS = {
    'node_modules',  # Librerie npm - NON TOCCARE
    'venv',          # Ambiente Python - NON TOCCARE
    '.git',          # Repository Git
    '__pycache__',   # Cache Python
    '.pytest_cache',
    'dist',
    'build',
    '.next',
    '.venv',
    'env'
}

# Nomi da cercare (case-insensitive)
PROBLEMATIC_NAMES = {
    'nul', 'null',
    'con', 'prn', 'aux',
    'com1', 'com2', 'com3', 'com4', 'com5', 'com6', 'com7', 'com8', 'com9',
    'lpt1', 'lpt2', 'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9'
}

# =================================================================
# FUNZIONI
# =================================================================

def is_protected_path(path: Path, protect_dirs: bool = True) -> bool:
    """
    Verifica se un path è protetto e non deve essere toccato.

    Args:
        path: Path da verificare
        protect_dirs: Se True, protegge node_modules/venv

    Returns:
        True se il path è protetto
    """
    if not protect_dirs:
        return False

    path_str = str(path).replace('\\', '/')

    for protected in PROTECTED_DIRS:
        if f'/{protected}/' in path_str or path_str.endswith(f'/{protected}'):
            return True

    return False


def is_problematic_name(name: str) -> bool:
    """
    Verifica se un nome contiene parole problematiche.

    Args:
        name: Nome da verificare

    Returns:
        True se contiene nomi problematici
    """
    name_lower = name.lower()

    # Controlla nome esatto
    base_name = Path(name).stem.lower()
    if base_name in PROBLEMATIC_NAMES:
        return True

    # Controlla se contiene le parole (con separatori)
    for problematic in PROBLEMATIC_NAMES:
        # Cerca con separatori
        if name_lower == problematic:
            return True
        if name_lower.startswith(f"{problematic}_"):
            return True
        if name_lower.startswith(f"{problematic}-"):
            return True
        if name_lower.startswith(f"{problematic}."):
            return True
        if f"_{problematic}_" in name_lower:
            return True
        if f"-{problematic}-" in name_lower:
            return True
        if f"_{problematic}." in name_lower:
            return True
        if f"-{problematic}." in name_lower:
            return True

    return False


def scan_directory(root_dir: str = ".", protect_dirs: bool = True):
    """
    Scansiona directory cercando file/cartelle problematici.

    Args:
        root_dir: Directory radice
        protect_dirs: Se True, protegge node_modules/venv

    Returns:
        Tuple (problematic_paths, protected_paths)
    """
    problematic = []
    protected = []
    count = 0

    print(f"\n[*] Scansionando: {os.path.abspath(root_dir)}")
    if protect_dirs:
        print(f"[*] Proteggendo: {', '.join(PROTECTED_DIRS)}")
    else:
        print("[!] ATTENZIONE: NESSUNA PROTEZIONE - Eliminerà TUTTO!")
    print()

    for root, dirs, files in os.walk(root_dir):
        root_path = Path(root)
        count += 1

        if count % 1000 == 0:
            print(f"    ... {count} directory controllate ...")

        # Controlla se questa directory è protetta
        if is_protected_path(root_path, protect_dirs):
            # Salta questa directory e tutte le sue sottodirectory
            dirs.clear()
            continue

        # Controlla nomi directory
        for dir_name in dirs[:]:
            dir_path = root_path / dir_name

            if is_protected_path(dir_path, protect_dirs):
                # Directory protetta - non entrare
                dirs.remove(dir_name)
                if is_problematic_name(dir_name):
                    protected.append(('dir', str(dir_path)))
                    print(f"[PROTETTA] {dir_path}")
                continue

            if is_problematic_name(dir_name):
                problematic.append(('dir', str(dir_path)))
                print(f"[TROVATA DIR] {dir_path}")

        # Controlla nomi file
        for file_name in files:
            file_path = root_path / file_name

            if is_protected_path(file_path, protect_dirs):
                if is_problematic_name(file_name):
                    protected.append(('file', str(file_path)))
                continue

            if is_problematic_name(file_name):
                problematic.append(('file', str(file_path)))
                print(f"[TROVATO FILE] {file_path}")

    return problematic, protected


def remove_problematic(items: list, dry_run: bool = True):
    """
    Rimuove file/directory problematici.

    Args:
        items: Lista di (tipo, path) da rimuovere
        dry_run: Se True, simula senza eliminare

    Returns:
        Numero di elementi eliminati
    """
    if not items:
        print("\n[OK] Nessun elemento da rimuovere")
        return 0

    print(f"\n{'[SIMULAZIONE] ' if dry_run else '[ELIMINAZIONE] '}Rimuovendo {len(items)} elementi...")
    print()

    removed = 0
    errors = 0

    for item_type, item_path in items:
        try:
            if dry_run:
                print(f"  [SIMULA] Rimuoverei {item_type}: {item_path}")
                removed += 1
            else:
                path = Path(item_path)

                if item_type == 'file' and path.is_file():
                    path.unlink()
                    print(f"  [OK] Rimosso file: {item_path}")
                    removed += 1
                elif item_type == 'dir' and path.is_dir():
                    shutil.rmtree(path)
                    print(f"  [OK] Rimossa directory: {item_path}")
                    removed += 1
                else:
                    print(f"  [SKIP] Non esiste più: {item_path}")

        except Exception as e:
            print(f"  [ERRORE] {item_path}: {e}")
            errors += 1

    print()
    print(f"[OK] Rimossi: {removed}")
    if errors > 0:
        print(f"[!] Errori: {errors}")

    return removed


def print_report(problematic: list, protected: list, protect_dirs: bool):
    """Stampa report finale"""
    print("\n" + "="*70)
    print("REPORT FINALE")
    print("="*70)

    if not problematic and not protected:
        print("\n[OK] NESSUN FILE PROBLEMATICO TROVATO!")
        print("\nIl progetto è completamente pulito.")
        print("="*70)
        return

    if problematic:
        print(f"\n[!] TROVATI {len(problematic)} elementi problematici DA RIMUOVERE:")
        print()
        for item_type, item_path in problematic:
            print(f"  [{item_type.upper()}] {item_path}")

    if protected:
        print(f"\n[PROTETTI] {len(protected)} elementi in directory protette:")
        print()
        for item_type, item_path in protected:
            print(f"  [{item_type.upper()}] {item_path}")

        if protect_dirs:
            print("\nQUESTI FILE SONO IN NODE_MODULES/VENV - NON VERRANNO TOCCATI!")
            print("Soluzione: Escludi node_modules da OneDrive (vedi FIX_ONEDRIVE_SYNC.md)")

    print("\n" + "="*70)


# =================================================================
# MAIN
# =================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Rimuove file/directory con 'nul' nel nome",
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--scan',
        action='store_true',
        help='Solo scansione (default)'
    )

    parser.add_argument(
        '--fix',
        action='store_true',
        help='Elimina file problematici (PROTEGGE node_modules/venv)'
    )

    parser.add_argument(
        '--fix-all',
        action='store_true',
        help='Elimina TUTTO anche in node_modules (PERICOLOSO!)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simula senza eliminare'
    )

    args = parser.parse_args()

    # Default: solo scansione
    if not args.fix and not args.fix_all:
        args.scan = True

    try:
        # Determina se proteggere directory
        protect = not args.fix_all

        # Scansiona
        print("\n" + "="*70)
        print("RICERCA FILE/DIRECTORY PROBLEMATICI")
        print("="*70)

        problematic, protected = scan_directory(".", protect_dirs=protect)

        # Report
        print_report(problematic, protected, protect)

        # Azioni
        if args.fix or args.fix_all:
            if not args.dry_run and problematic:
                # Conferma
                print("\n[!] ATTENZIONE: Stai per ELIMINARE permanentemente i file!")
                if args.fix_all:
                    print("[!] ATTENZIONE: Eliminerai ANCHE file in node_modules!")
                    print("[!] Questo ROMPERÀ l'applicazione frontend!")

                risposta = input("\nContinuare? (scrivi 'SI' per confermare): ")
                if risposta != 'SI':
                    print("\nOperazione annullata.")
                    return 0

            # Elimina
            removed = remove_problematic(problematic, dry_run=args.dry_run)

            if removed > 0 and not args.dry_run:
                print("\n[OK] File eliminati con successo!")

                if protected:
                    print("\n[INFO] File protetti rimasti:")
                    print("       Escludi node_modules da OneDrive per risolvere.")
                    print("       Vedi: FIX_ONEDRIVE_SYNC.md")

        # Exit code
        return 1 if problematic else 0

    except KeyboardInterrupt:
        print("\n\n[!] Operazione interrotta")
        return 2
    except Exception as e:
        print(f"\n[ERRORE] {e}")
        import traceback
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
