#!/usr/bin/env python3
"""
Cerca ESATTAMENTE file/cartelle chiamati 'null' o 'nul'
"""
import os
import sys

def search_exact(root_dir="."):
    """Cerca file/cartelle con nome ESATTO 'null' o 'nul'"""
    problematic = []
    count = 0

    print(f"Cercando in {os.path.abspath(root_dir)}...")
    print()

    for root, dirs, files in os.walk(root_dir):
        count += 1
        if count % 1000 == 0:
            print(f"  ... controllate {count} directory ...")

        # Controlla directory
        for d in dirs:
            if d.lower() in ['null', 'nul']:
                path = os.path.join(root, d)
                print(f"[!] TROVATA DIRECTORY: {path}")
                problematic.append(('dir', path))

        # Controlla file
        for f in files:
            # Nome esatto (con o senza estensione)
            name_lower = f.lower()
            base_name = os.path.splitext(f)[0].lower()

            if name_lower in ['null', 'nul'] or base_name in ['null', 'nul']:
                path = os.path.join(root, f)
                print(f"[!] TROVATO FILE: {path}")
                problematic.append(('file', path))

    return problematic

if __name__ == "__main__":
    print("="*70)
    print("RICERCA ESATTA FILE/DIRECTORY 'null' o 'nul'")
    print("="*70)
    print()

    results = search_exact()

    print()
    print("="*70)
    print("RISULTATI")
    print("="*70)

    if results:
        print(f"\nTrovati {len(results)} elementi problematici:\n")
        for tipo, path in results:
            print(f"  [{tipo.upper()}] {path}")

        print("\n" + "="*70)
        print("AZIONE RICHIESTA")
        print("="*70)
        print("\nPer eliminare questi file/directory, esegui:")
        print("  python scripts/remove_windows_reserved_names.py --fix")
        print("\nPer rinominare invece di eliminare:")
        print("  python scripts/remove_windows_reserved_names.py --rename")

    else:
        print("\n[OK] Nessun file o directory chiamato 'null' o 'nul' trovato!")
        print("\nIl progetto e' pulito.")

    print("="*70)

    sys.exit(1 if results else 0)
