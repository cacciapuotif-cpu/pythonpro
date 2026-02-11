#!/usr/bin/env python3
"""
Script di audit repository per identificare file duplicati e orfani

Analizza il progetto pythonpro e genera un report JSON con:
- File duplicati (stesso hash)
- File near-duplicates (stesso nome, contenuto simile)
- File orfani (non importati/mai referenziati)
- Proposte di rimozione con livelli di confidenza

Author: Claude Code
Date: 2025-10-19
"""

import os
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict
import re

# Configurazione
PROJECT_ROOT = Path(__file__).parent.parent
IGNORE_DIRS = {
    'venv', '__pycache__', '.git', 'node_modules', '.pytest_cache',
    'htmlcov', 'backups', 'logs', 'uploads', 'migrations', 'alembic'
}
IGNORE_EXTENSIONS = {'.pyc', '.pyo', '.db', '.sqlite', '.sqlite3', '.log'}
BACKEND_DIR = PROJECT_ROOT / 'backend'
FRONTEND_DIR = PROJECT_ROOT / 'frontend'


def calculate_file_hash(filepath: Path) -> str:
    """Calcola hash MD5 di un file"""
    try:
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception as e:
        print(f"Errore lettura {filepath}: {e}")
        return None


def get_all_files(root_dir: Path) -> List[Path]:
    """Recupera tutti i file del progetto escludendo directory ignorate"""
    files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Rimuovi directory da ignorare
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]

        for filename in filenames:
            filepath = Path(dirpath) / filename
            if filepath.suffix not in IGNORE_EXTENSIONS:
                files.append(filepath)

    return files


def find_duplicates(files: List[Path]) -> Dict[str, List[str]]:
    """Trova file duplicati per hash"""
    hash_map = defaultdict(list)

    for filepath in files:
        file_hash = calculate_file_hash(filepath)
        if file_hash:
            hash_map[file_hash].append(str(filepath.relative_to(PROJECT_ROOT)))

    # Filtra solo duplicati (hash con più file)
    duplicates = {h: paths for h, paths in hash_map.items() if len(paths) > 1}
    return duplicates


def find_near_duplicates(files: List[Path]) -> List[Dict]:
    """Trova file con stesso nome ma contenuto leggermente diverso"""
    name_map = defaultdict(list)

    for filepath in files:
        name_map[filepath.name].append(filepath)

    near_duplicates = []
    for filename, filepaths in name_map.items():
        if len(filepaths) > 1:
            # Confronta contenuto
            for i, fp1 in enumerate(filepaths):
                for fp2 in filepaths[i+1:]:
                    similarity = calculate_similarity(fp1, fp2)
                    if similarity > 0.7:  # 70% simili
                        near_duplicates.append({
                            'filename': filename,
                            'file1': str(fp1.relative_to(PROJECT_ROOT)),
                            'file2': str(fp2.relative_to(PROJECT_ROOT)),
                            'similarity': round(similarity, 2),
                            'suggestion': 'review'
                        })

    return near_duplicates


def calculate_similarity(file1: Path, file2: Path) -> float:
    """Calcola similarità tra due file (0.0 - 1.0)"""
    try:
        with open(file1, 'r', encoding='utf-8', errors='ignore') as f1:
            content1 = f1.read()
        with open(file2, 'r', encoding='utf-8', errors='ignore') as f2:
            content2 = f2.read()

        # Similarità semplice basata su lunghezza e contenuto comune
        lines1 = set(content1.splitlines())
        lines2 = set(content2.splitlines())

        if not lines1 or not lines2:
            return 0.0

        common_lines = lines1.intersection(lines2)
        total_lines = lines1.union(lines2)

        return len(common_lines) / len(total_lines) if total_lines else 0.0
    except Exception as e:
        return 0.0


def find_orphaned_files(files: List[Path]) -> List[Dict]:
    """Trova file Python orfani (non importati da nessun altro file)"""
    orphaned = []

    # Filtra solo file Python nel backend
    python_files = [f for f in files if f.suffix == '.py' and 'backend' in str(f)]

    # Crea set di tutti i nomi di modulo importati
    imported_modules = set()

    for pyfile in python_files:
        try:
            with open(pyfile, 'r', encoding='utf-8') as f:
                content = f.read()
                # Trova import statements
                imports = re.findall(r'(?:from|import)\s+([a-zA-Z_][a-zA-Z0-9_]*)', content)
                imported_modules.update(imports)
        except Exception:
            continue

    # Controlla quali file non sono mai importati
    for pyfile in python_files:
        module_name = pyfile.stem

        # Salta file speciali
        if module_name in ['__init__', 'main', 'manage', 'wsgi', 'asgi']:
            continue

        # Se il modulo non è mai importato, è orfano
        if module_name not in imported_modules:
            # Verifica se è un file di test
            is_test = 'test' in str(pyfile).lower()
            confidence = 'low' if is_test else 'medium'

            orphaned.append({
                'file': str(pyfile.relative_to(PROJECT_ROOT)),
                'module_name': module_name,
                'is_test_file': is_test,
                'confidence': confidence,
                'reason': 'Module never imported in codebase'
            })

    return orphaned


def find_backup_files(files: List[Path]) -> List[Dict]:
    """Trova file di backup evidenti"""
    backup_patterns = ['_backup', '_bak', '_old', '_temp', '_copy', '.bak', '.old']
    backup_files = []

    for filepath in files:
        filename = filepath.name.lower()
        stem = filepath.stem.lower()

        for pattern in backup_patterns:
            if pattern in filename or pattern in stem:
                backup_files.append({
                    'file': str(filepath.relative_to(PROJECT_ROOT)),
                    'pattern': pattern,
                    'confidence': 'high',
                    'suggestion': 'safe to delete',
                    'reason': f'Matches backup pattern: {pattern}'
                })
                break

    return backup_files


def generate_removal_suggestions(duplicates: Dict, near_duplicates: List,
                                 orphaned: List, backups: List) -> List[Dict]:
    """Genera suggerimenti di rimozione con confidenza"""
    suggestions = []

    # Duplicati esatti - confidenza alta
    for file_hash, paths in duplicates.items():
        # Mantieni il primo, suggerisci rimozione degli altri
        for path in paths[1:]:
            suggestions.append({
                'file': path,
                'type': 'exact_duplicate',
                'confidence': 'high',
                'action': 'delete',
                'reason': f'Exact duplicate of {paths[0]}',
                'original': paths[0]
            })

    # Near duplicates - richiede review
    for nd in near_duplicates:
        suggestions.append({
            'file': nd['file2'],
            'type': 'near_duplicate',
            'confidence': 'review',
            'action': 'review and merge',
            'reason': f'{int(nd["similarity"]*100)}% similar to {nd["file1"]}',
            'original': nd['file1']
        })

    # File orfani - confidenza media/bassa
    for orphan in orphaned:
        suggestions.append({
            'file': orphan['file'],
            'type': 'orphaned',
            'confidence': orphan['confidence'],
            'action': 'review' if orphan['is_test_file'] else 'consider delete',
            'reason': orphan['reason']
        })

    # File di backup - confidenza alta
    for backup in backups:
        suggestions.append({
            'file': backup['file'],
            'type': 'backup',
            'confidence': backup['confidence'],
            'action': 'delete',
            'reason': backup['reason']
        })

    return suggestions


def main():
    """Funzione principale di audit"""
    print("=" * 70)
    print("AUDIT REPOSITORY - pythonpro")
    print("=" * 70)
    print()

    # Raccogli tutti i file
    print("[*] Scansione file nel progetto...")
    all_files = get_all_files(PROJECT_ROOT)
    print(f"   Trovati {len(all_files)} file da analizzare\n")

    # Trova duplicati
    print("[*] Ricerca duplicati esatti...")
    duplicates = find_duplicates(all_files)
    print(f"   Trovati {len(duplicates)} gruppi di duplicati\n")

    # Trova near duplicates
    print("[*] Ricerca near-duplicates...")
    near_duplicates = find_near_duplicates(all_files)
    print(f"   Trovate {len(near_duplicates)} coppie near-duplicate\n")

    # Trova file orfani
    print("[*] Ricerca file orfani...")
    orphaned = find_orphaned_files(all_files)
    print(f"   Trovati {len(orphaned)} file potenzialmente orfani\n")

    # Trova file di backup
    print("[*] Ricerca file di backup...")
    backup_files = find_backup_files(all_files)
    print(f"   Trovati {len(backup_files)} file di backup\n")

    # Genera suggerimenti
    print("[*] Generazione suggerimenti di pulizia...")
    suggestions = generate_removal_suggestions(duplicates, near_duplicates, orphaned, backup_files)
    print(f"   Generati {len(suggestions)} suggerimenti\n")

    # Prepara report
    report = {
        'audit_date': '2025-10-19',
        'project_root': str(PROJECT_ROOT),
        'summary': {
            'total_files_scanned': len(all_files),
            'exact_duplicates': len(duplicates),
            'near_duplicates': len(near_duplicates),
            'orphaned_files': len(orphaned),
            'backup_files': len(backup_files),
            'total_suggestions': len(suggestions)
        },
        'duplicates': {
            file_hash: {
                'files': paths,
                'count': len(paths)
            }
            for file_hash, paths in duplicates.items()
        },
        'near_duplicates': near_duplicates,
        'orphaned_files': orphaned,
        'backup_files': backup_files,
        'removal_suggestions': suggestions,
        'confidence_levels': {
            'high': sum(1 for s in suggestions if s['confidence'] == 'high'),
            'medium': sum(1 for s in suggestions if s['confidence'] == 'medium'),
            'low': sum(1 for s in suggestions if s['confidence'] == 'low'),
            'review': sum(1 for s in suggestions if s['confidence'] == 'review')
        }
    }

    # Salva report
    output_file = PROJECT_ROOT / 'docs' / 'audit_report.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("=" * 70)
    print(f"[OK] Audit completato!")
    print(f"[FILE] Report salvato in: {output_file}")
    print()
    print("RIEPILOGO:")
    print(f"  - File totali scansionati: {len(all_files)}")
    print(f"  - Duplicati esatti: {len(duplicates)} gruppi")
    print(f"  - Near-duplicates: {len(near_duplicates)} coppie")
    print(f"  - File orfani: {len(orphaned)}")
    print(f"  - File di backup: {len(backup_files)}")
    print()
    print("CONFIDENZA SUGGERIMENTI:")
    print(f"  - Alta (safe to delete): {report['confidence_levels']['high']}")
    print(f"  - Media (review first): {report['confidence_levels']['medium']}")
    print(f"  - Bassa (careful review): {report['confidence_levels']['low']}")
    print(f"  - Review richiesta: {report['confidence_levels']['review']}")
    print("=" * 70)


if __name__ == '__main__':
    main()
