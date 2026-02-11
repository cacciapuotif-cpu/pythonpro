#!/usr/bin/env python3
"""
Script rapido per trovare file "null" o "nul"
"""
import os
from pathlib import Path

# Directory da escludere
EXCLUDE = {'node_modules', 'venv', '.git', '__pycache__', '.venv', 'env'}

def find_null_files(root_dir="."):
    """Trova tutti i file con 'null' o 'nul' nel nome"""
    found = []

    for root, dirs, files in os.walk(root_dir):
        # Rimuovi directory da escludere
        dirs[:] = [d for d in dirs if d not in EXCLUDE]

        # Controlla ogni file
        for file in files:
            name_lower = file.lower()
            if 'null' in name_lower or name_lower == 'nul':
                full_path = os.path.join(root, file)
                found.append(full_path)
                print(f"[TROVATO FILE] {full_path}")

        # Controlla ogni directory
        for dir_name in dirs:
            name_lower = dir_name.lower()
            if 'null' in name_lower or name_lower == 'nul':
                full_path = os.path.join(root, dir_name)
                found.append(full_path)
                print(f"[TROVATA DIR] {full_path}")

    return found

if __name__ == "__main__":
    print("Cercando file/cartelle con 'null' o 'nul' nel nome...")
    print()

    results = find_null_files()

    print()
    print("="*70)
    if results:
        print(f"Trovati {len(results)} file/cartelle:")
        for r in results:
            print(f"  - {r}")
    else:
        print("Nessun file/cartella con 'null' o 'nul' trovato")
    print("="*70)
