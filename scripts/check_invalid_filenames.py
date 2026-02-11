#!/usr/bin/env python3
"""
Script per verificare la presenza di file o directory con nomi problematici.

Questo script cerca file/cartelle con nomi come "null", "None", "undefined"
che possono causare problemi di sincronizzazione con OneDrive.

Uso:
    python scripts/check_null_filenames.py
    python scripts/check_null_filenames.py --fix  # Rinomina file problematici
    python scripts/check_null_filenames.py --exclude node_modules venv

Exit codes:
    0 - Nessun file problematico trovato
    1 - File problematici trovati
    2 - Errore durante l'esecuzione
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Set


# Nomi problematici da cercare
PROBLEMATIC_NAMES = {
    'null',
    'None',
    'undefined',
    'NULL',
    'NONE',
    'UNDEFINED'
}

# Directory da escludere di default
DEFAULT_EXCLUDES = {
    'node_modules',
    'venv',
    '.git',
    '__pycache__',
    '.pytest_cache',
    'dist',
    'build',
    '.next'
}


class NullFilenameChecker:
    """Controlla e gestisce file con nomi problematici"""

    def __init__(self, root_dir: str = ".", excludes: Set[str] = None):
        self.root_dir = Path(root_dir).resolve()
        self.excludes = excludes or DEFAULT_EXCLUDES
        self.problematic_files: List[Path] = []

    def should_exclude(self, path: Path) -> bool:
        """Verifica se il path deve essere escluso"""
        return any(exclude in path.parts for exclude in self.excludes)

    def is_problematic_name(self, name: str) -> bool:
        """Verifica se un nome è problematico"""
        # Controlla nome esatto
        if name in PROBLEMATIC_NAMES:
            return True

        # Controlla nome senza estensione
        stem = Path(name).stem
        if stem in PROBLEMATIC_NAMES:
            return True

        return False

    def scan(self) -> List[Path]:
        """
        Scansiona il progetto cercando file/cartelle problematici

        Returns:
            Lista di Path con nomi problematici
        """
        print(f"Scansionando {self.root_dir}...")
        print(f"Escludendo: {', '.join(self.excludes)}\n")

        for root, dirs, files in os.walk(self.root_dir):
            root_path = Path(root)

            # Escludi directory
            if self.should_exclude(root_path):
                dirs.clear()  # Non scendere nelle sottodirectory
                continue

            # Controlla nomi directory
            for dir_name in dirs[:]:  # Usa slice per modificare durante iterazione
                if self.is_problematic_name(dir_name):
                    problematic_path = root_path / dir_name
                    self.problematic_files.append(problematic_path)
                    print(f"[X] DIRECTORY: {problematic_path}")
                    # Non escludere, potremmo voler rinominare

            # Controlla nomi file
            for file_name in files:
                if self.is_problematic_name(file_name):
                    problematic_path = root_path / file_name
                    self.problematic_files.append(problematic_path)
                    print(f"[X] FILE: {problematic_path}")

        return self.problematic_files

    def generate_safe_name(self, original_path: Path) -> str:
        """
        Genera un nome sicuro per un file/directory problematico

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

    def fix(self, dry_run: bool = True) -> int:
        """
        Rinomina i file/directory problematici

        Args:
            dry_run: Se True, mostra solo cosa farebbe senza eseguire

        Returns:
            Numero di file rinominati
        """
        if not self.problematic_files:
            print("\n[OK] Nessun file da rinominare")
            return 0

        print(f"\n{'[DRY RUN] ' if dry_run else ''}Rinominando {len(self.problematic_files)} file...")

        renamed_count = 0
        for old_path in self.problematic_files:
            try:
                new_name = self.generate_safe_name(old_path)
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
                    print(f"  {old_path.name} -> {new_name}")
                else:
                    old_path.rename(new_path)
                    print(f"  [OK] {old_path.name} -> {new_name}")
                    renamed_count += 1

            except Exception as e:
                print(f"  [ERROR] Errore rinominando {old_path}: {e}", file=sys.stderr)

        return renamed_count

    def report(self) -> None:
        """Stampa un report dei risultati"""
        print("\n" + "="*70)
        print("REPORT")
        print("="*70)

        if not self.problematic_files:
            print("[OK] Nessun file o directory con nome problematico trovato!")
            print("\nIl progetto e' conforme alle best practice per OneDrive.")
        else:
            print(f"[WARNING] Trovati {len(self.problematic_files)} file/directory problematici:")
            print("\nQuesti file possono causare problemi con OneDrive.")
            print("Usa --fix per rinominarli automaticamente.")
            print("\nPer maggiori informazioni, vedi PREVENT_NULL_FILENAMES.md")

        print("="*70)


def main():
    parser = argparse.ArgumentParser(
        description="Controlla file/directory con nomi problematici per OneDrive",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--fix',
        action='store_true',
        help='Rinomina automaticamente file problematici'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Mostra cosa verrebbe rinominato senza eseguire (richiede --fix)'
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

    args = parser.parse_args()

    try:
        # Crea checker e scansiona
        checker = NullFilenameChecker(
            root_dir=args.root,
            excludes=set(args.exclude)
        )

        problematic = checker.scan()

        # Se richiesto, rinomina
        if args.fix or args.dry_run:
            checker.fix(dry_run=args.dry_run)

        # Stampa report
        checker.report()

        # Exit code
        return 1 if problematic else 0

    except KeyboardInterrupt:
        print("\n\nInterrotto dall'utente", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"\n❌ Errore: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
