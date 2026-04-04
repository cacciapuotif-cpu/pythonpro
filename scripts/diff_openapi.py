#!/usr/bin/env python3
"""
Script per confrontare schema OpenAPI generato da FastAPI con skeleton di riferimento

Estrae lo schema OpenAPI dal backend FastAPI in esecuzione e lo confronta con
uno schema skeleton di riferimento, generando un diff leggibile.

Author: Claude Code
Date: 2025-10-19
"""

import json
import requests
import yaml
from pathlib import Path
from typing import Dict, List, Set, Any
from datetime import datetime

# Configurazione
PROJECT_ROOT = Path(__file__).parent.parent
DOCS_DIR = PROJECT_ROOT / 'docs'
API_URL = 'http://localhost:8001'  # URL del backend in esecuzione
OPENAPI_ENDPOINT = f'{API_URL}/openapi.json'
SKELETON_FILE = DOCS_DIR / 'openapi_skeleton.yaml'
DIFF_OUTPUT = DOCS_DIR / 'OPENAPI_DIFF.md'


def fetch_openapi_schema() -> Dict:
    """Recupera schema OpenAPI dal backend FastAPI"""
    try:
        print(f"[*] Connessione a {OPENAPI_ENDPOINT}...")
        response = requests.get(OPENAPI_ENDPOINT, timeout=10)
        response.raise_for_status()
        schema = response.json()
        print("[OK] Schema OpenAPI recuperato con successo")
        return schema
    except requests.exceptions.ConnectionError:
        print("[ERROR] Errore: Backend FastAPI non raggiungibile")
        print(f"   Assicurati che il server sia in esecuzione su {API_URL}")
        return None
    except Exception as e:
        print(f"[ERROR] Errore durante il recupero schema: {e}")
        return None


def load_skeleton_schema() -> Dict:
    """Carica schema skeleton di riferimento"""
    if not SKELETON_FILE.exists():
        print(f"[WARN] File skeleton non trovato: {SKELETON_FILE}")
        print("   Creazione skeleton vuoto...")
        return create_empty_skeleton()

    try:
        with open(SKELETON_FILE, 'r', encoding='utf-8') as f:
            skeleton = yaml.safe_load(f)
        print(f"[OK] Schema skeleton caricato da {SKELETON_FILE}")
        return skeleton
    except Exception as e:
        print(f"[ERROR] Errore caricamento skeleton: {e}")
        return create_empty_skeleton()


def create_empty_skeleton() -> Dict:
    """Crea uno skeleton vuoto minimale"""
    return {
        'openapi': '3.0.0',
        'info': {
            'title': 'Gestionale Collaboratori API',
            'version': '2.0.0'
        },
        'paths': {},
        'components': {
            'schemas': {}
        }
    }


def save_skeleton(schema: Dict):
    """Salva schema come skeleton YAML"""
    DOCS_DIR.mkdir(exist_ok=True)

    # Rimuovi campi generati automaticamente
    clean_schema = {
        'openapi': schema.get('openapi', '3.0.0'),
        'info': schema.get('info', {}),
        'paths': schema.get('paths', {}),
        'components': schema.get('components', {})
    }

    with open(SKELETON_FILE, 'w', encoding='utf-8') as f:
        yaml.dump(clean_schema, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"[SAVE] Skeleton salvato in {SKELETON_FILE}")


def extract_endpoints(schema: Dict) -> Set[str]:
    """Estrae lista endpoint da schema OpenAPI"""
    endpoints = set()
    paths = schema.get('paths', {})

    for path, methods in paths.items():
        for method in methods.keys():
            if method.upper() in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                endpoints.add(f"{method.upper()} {path}")

    return endpoints


def compare_schemas(current: Dict, skeleton: Dict) -> Dict:
    """Confronta schema corrente con skeleton"""
    current_endpoints = extract_endpoints(current)
    skeleton_endpoints = extract_endpoints(skeleton)

    added = current_endpoints - skeleton_endpoints
    removed = skeleton_endpoints - current_endpoints
    unchanged = current_endpoints & skeleton_endpoints

    current_schemas = set(current.get('components', {}).get('schemas', {}).keys())
    skeleton_schemas = set(skeleton.get('components', {}).get('schemas', {}).keys())

    added_schemas = current_schemas - skeleton_schemas
    removed_schemas = skeleton_schemas - current_schemas

    return {
        'endpoints': {
            'added': sorted(list(added)),
            'removed': sorted(list(removed)),
            'unchanged': sorted(list(unchanged)),
            'total_current': len(current_endpoints),
            'total_skeleton': len(skeleton_endpoints)
        },
        'schemas': {
            'added': sorted(list(added_schemas)),
            'removed': sorted(list(removed_schemas)),
            'total_current': len(current_schemas),
            'total_skeleton': len(skeleton_schemas)
        }
    }


def organize_endpoints_by_domain(endpoints: List[str]) -> Dict[str, List[str]]:
    """Organizza endpoint per dominio (prefix)"""
    domains = {}

    for endpoint in endpoints:
        method, path = endpoint.split(' ', 1)

        # Estrai dominio dal path
        if path.startswith('/api/v1/'):
            parts = path.split('/')
            domain = parts[3] if len(parts) > 3 else 'root'
        elif path.startswith('/'):
            domain = 'system'
        else:
            domain = 'unknown'

        if domain not in domains:
            domains[domain] = []

        domains[domain].append(endpoint)

    # Ordina gli endpoint in ogni dominio
    for domain in domains:
        domains[domain].sort()

    return domains


def generate_diff_report(comparison: Dict, current_schema: Dict, skeleton_schema: Dict):
    """Genera report di confronto in Markdown"""
    report_lines = [
        "# OpenAPI Schema Diff Report",
        "",
        f"**Data generazione:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "---",
        "",
        "## [STATS] Riepilogo",
        "",
        f"- **Endpoint totali correnti:** {comparison['endpoints']['total_current']}",
        f"- **Endpoint totali skeleton:** {comparison['endpoints']['total_skeleton']}",
        f"- **Endpoint aggiunti:** {len(comparison['endpoints']['added'])}",
        f"- **Endpoint rimossi:** {len(comparison['endpoints']['removed'])}",
        f"- **Endpoint invariati:** {len(comparison['endpoints']['unchanged'])}",
        "",
        f"- **Schema totali correnti:** {comparison['schemas']['total_current']}",
        f"- **Schema totali skeleton:** {comparison['schemas']['total_skeleton']}",
        f"- **Schema aggiunti:** {len(comparison['schemas']['added'])}",
        f"- **Schema rimossi:** {len(comparison['schemas']['removed'])}",
        "",
        "---",
        ""
    ]

    # Endpoint aggiunti
    if comparison['endpoints']['added']:
        report_lines.extend([
            f"## [OK] Endpoint Aggiunti ({len(comparison['endpoints']['added'])})",
            "",
            "Nuovi endpoint implementati non presenti nello skeleton:",
            ""
        ])

        # Organizza per dominio
        domains = organize_endpoints_by_domain(comparison['endpoints']['added'])
        for domain, endpoints in sorted(domains.items()):
            report_lines.append(f"### Domain: `{domain}`")
            report_lines.append("")
            for endpoint in endpoints:
                method, path = endpoint.split(' ', 1)
                report_lines.append(f"- **{method}** `{path}`")
            report_lines.append("")
    else:
        report_lines.extend([
            "## [OK] Endpoint Aggiunti",
            "",
            "_Nessun nuovo endpoint_",
            ""
        ])

    # Endpoint rimossi
    if comparison['endpoints']['removed']:
        report_lines.extend([
            f"## [REMOVED] Endpoint Rimossi ({len(comparison['endpoints']['removed'])})",
            "",
            "Endpoint presenti nello skeleton ma non pi[*] implementati:",
            ""
        ])

        domains = organize_endpoints_by_domain(comparison['endpoints']['removed'])
        for domain, endpoints in sorted(domains.items()):
            report_lines.append(f"### Domain: `{domain}`")
            report_lines.append("")
            for endpoint in endpoints:
                method, path = endpoint.split(' ', 1)
                report_lines.append(f"- **{method}** `{path}`")
            report_lines.append("")
    else:
        report_lines.extend([
            "## [REMOVED] Endpoint Rimossi",
            "",
            "_Nessun endpoint rimosso_",
            ""
        ])

    # Schema aggiunti
    if comparison['schemas']['added']:
        report_lines.extend([
            f"## [SCHEMA] Schema Aggiunti ({len(comparison['schemas']['added'])})",
            "",
            "Nuovi modelli Pydantic definiti:",
            ""
        ])
        for schema in comparison['schemas']['added']:
            report_lines.append(f"- `{schema}`")
        report_lines.append("")
    else:
        report_lines.extend([
            "## [SCHEMA] Schema Aggiunti",
            "",
            "_Nessun nuovo schema_",
            ""
        ])

    # Schema rimossi
    if comparison['schemas']['removed']:
        report_lines.extend([
            f"## [DELETED] Schema Rimossi ({len(comparison['schemas']['removed'])})",
            "",
            "Schema non pi[*] presenti nell'implementazione:",
            ""
        ])
        for schema in comparison['schemas']['removed']:
            report_lines.append(f"- `{schema}`")
        report_lines.append("")
    else:
        report_lines.extend([
            "## [DELETED] Schema Rimossi",
            "",
            "_Nessuno schema rimosso_",
            ""
        ])

    # Endpoint invariati (overview)
    if comparison['endpoints']['unchanged']:
        report_lines.extend([
            f"## [CHECK] Endpoint Invariati ({len(comparison['endpoints']['unchanged'])})",
            "",
            "<details>",
            "<summary>Mostra lista completa endpoint invariati</summary>",
            ""
        ])

        domains = organize_endpoints_by_domain(comparison['endpoints']['unchanged'])
        for domain, endpoints in sorted(domains.items()):
            report_lines.append(f"### Domain: `{domain}`")
            report_lines.append("")
            for endpoint in endpoints:
                method, path = endpoint.split(' ', 1)
                report_lines.append(f"- **{method}** `{path}`")
            report_lines.append("")

        report_lines.extend([
            "</details>",
            ""
        ])

    # Informazioni versione
    report_lines.extend([
        "---",
        "",
        "## [INFO] Informazioni Versione",
        "",
        "### Schema Corrente",
        f"- **OpenAPI Version:** {current_schema.get('openapi', 'N/A')}",
        f"- **API Title:** {current_schema.get('info', {}).get('title', 'N/A')}",
        f"- **API Version:** {current_schema.get('info', {}).get('version', 'N/A')}",
        "",
        "### Schema Skeleton",
        f"- **OpenAPI Version:** {skeleton_schema.get('openapi', 'N/A')}",
        f"- **API Title:** {skeleton_schema.get('info', {}).get('title', 'N/A')}",
        f"- **API Version:** {skeleton_schema.get('info', {}).get('version', 'N/A')}",
        ""
    ])

    # Salva report
    DOCS_DIR.mkdir(exist_ok=True)
    with open(DIFF_OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))

    print(f"[*] Report diff salvato in {DIFF_OUTPUT}")


def main():
    """Funzione principale"""
    print("=" * 70)
    print("OPENAPI SCHEMA DIFF")
    print("=" * 70)
    print()

    # Recupera schema corrente
    current_schema = fetch_openapi_schema()
    if not current_schema:
        print("\n[WARN]  Impossibile procedere senza schema corrente")
        print("   Avvia il backend FastAPI e riprova")
        return

    # Carica skeleton
    skeleton_schema = load_skeleton_schema()

    # Se skeleton non esiste, crealo dal corrente
    if not SKELETON_FILE.exists():
        print("\n[*] Creazione skeleton iniziale dallo schema corrente...")
        save_skeleton(current_schema)
        skeleton_schema = current_schema

    # Confronta
    print("\n[*] Confronto schema corrente con skeleton...")
    comparison = compare_schemas(current_schema, skeleton_schema)

    # Genera report
    print("\n[*] Generazione report diff...")
    generate_diff_report(comparison, current_schema, skeleton_schema)

    print("\n" + "=" * 70)
    print("[OK] Diff completato!")
    print(f"[FILE] Report disponibile in: {DIFF_OUTPUT}")
    print("=" * 70)


if __name__ == '__main__':
    main()
