#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================
STRESS TEST SCRIPT PER GESTIONALE
=================================================================
Esegue test di carico simulando utenti concorrenti e operazioni
multiple per verificare stabilità sotto stress.
=================================================================
"""

import sys
import io
# Fix encoding Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import requests
import time
import json
import concurrent.futures
from datetime import datetime
import sys

# Configurazione
BASE_URL = "http://localhost:8000"
NUM_THREADS = 10
REQUESTS_PER_THREAD = 50
TIMEOUT = 5

# Statistiche
stats = {
    "total_requests": 0,
    "successful": 0,
    "failed": 0,
    "total_time": 0,
    "errors": []
}

def test_health():
    """Test health endpoint"""
    try:
        start = time.time()
        response = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
        elapsed = time.time() - start

        stats["total_requests"] += 1
        stats["total_time"] += elapsed

        if response.status_code == 200:
            stats["successful"] += 1
            return True
        else:
            stats["failed"] += 1
            stats["errors"].append(f"Health check failed: {response.status_code}")
            return False
    except Exception as e:
        stats["failed"] += 1
        stats["errors"].append(f"Health check error: {str(e)}")
        return False

def test_get_collaborators():
    """Test GET collaborators endpoint"""
    try:
        start = time.time()
        response = requests.get(f"{BASE_URL}/collaborators/", timeout=TIMEOUT)
        elapsed = time.time() - start

        stats["total_requests"] += 1
        stats["total_time"] += elapsed

        if response.status_code == 200:
            stats["successful"] += 1
            return True
        else:
            stats["failed"] += 1
            return False
    except Exception as e:
        stats["failed"] += 1
        stats["errors"].append(f"GET collaborators error: {str(e)}")
        return False

def test_get_projects():
    """Test GET projects endpoint"""
    try:
        start = time.time()
        response = requests.get(f"{BASE_URL}/projects/", timeout=TIMEOUT)
        elapsed = time.time() - start

        stats["total_requests"] += 1
        stats["total_time"] += elapsed

        if response.status_code == 200:
            stats["successful"] += 1
            return True
        else:
            stats["failed"] += 1
            return False
    except Exception as e:
        stats["failed"] += 1
        stats["errors"].append(f"GET projects error: {str(e)}")
        return False

def test_create_collaborator(thread_id, request_id):
    """Test POST collaborator endpoint"""
    try:
        data = {
            "first_name": f"Stress",
            "last_name": f"Test_{thread_id}_{request_id}",
            "email": f"stress.test.{thread_id}.{request_id}@test.com",
            "phone": f"{thread_id}{request_id:04d}",
            "position": "Tester"
        }

        start = time.time()
        response = requests.post(
            f"{BASE_URL}/collaborators/",
            json=data,
            timeout=TIMEOUT
        )
        elapsed = time.time() - start

        stats["total_requests"] += 1
        stats["total_time"] += elapsed

        if response.status_code in [200, 201]:
            stats["successful"] += 1
            return True
        else:
            stats["failed"] += 1
            return False
    except Exception as e:
        stats["failed"] += 1
        stats["errors"].append(f"CREATE collaborator error: {str(e)}")
        return False

def worker_thread(thread_id):
    """Worker thread che esegue richieste multiple"""
    print(f"Thread {thread_id} started")

    for i in range(REQUESTS_PER_THREAD):
        # Mix di operazioni
        test_health()
        test_get_collaborators()
        test_get_projects()

        # Ogni 10 richieste, crea un collaboratore
        if i % 10 == 0:
            test_create_collaborator(thread_id, i)

    print(f"Thread {thread_id} completed")

def print_progress_bar(iteration, total, prefix='', suffix='', length=50):
    """Stampa barra di progresso"""
    percent = f"{100 * (iteration / float(total)):.1f}"
    filled_length = int(length * iteration // total)
    bar = '█' * filled_length + '-' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end='')
    if iteration == total:
        print()

def main():
    print("=" * 70)
    print("STRESS TEST - GESTIONALE")
    print("=" * 70)
    print(f"Configurazione:")
    print(f"  - URL Base: {BASE_URL}")
    print(f"  - Thread concorrenti: {NUM_THREADS}")
    print(f"  - Richieste per thread: {REQUESTS_PER_THREAD}")
    print(f"  - Richieste totali: {NUM_THREADS * REQUESTS_PER_THREAD * 3}")
    print(f"  - Timeout: {TIMEOUT}s")
    print("=" * 70)
    print()

    # Verifica che il sistema sia online
    print("Verificando che il sistema sia online...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print(f"❌ Sistema non raggiungibile: {response.status_code}")
            sys.exit(1)
        print("✅ Sistema online")
    except Exception as e:
        print(f"❌ Impossibile raggiungere il sistema: {e}")
        sys.exit(1)

    print()
    print("Avvio stress test...")
    start_time = time.time()

    # Esegui thread concorrenti
    with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        futures = [executor.submit(worker_thread, i) for i in range(NUM_THREADS)]
        concurrent.futures.wait(futures)

    end_time = time.time()
    total_elapsed = end_time - start_time

    # Statistiche finali
    print()
    print("=" * 70)
    print("RISULTATI STRESS TEST")
    print("=" * 70)
    print(f"Tempo totale: {total_elapsed:.2f}s")
    print(f"Richieste totali: {stats['total_requests']}")
    print(f"Richieste riuscite: {stats['successful']}")
    print(f"Richieste fallite: {stats['failed']}")
    print(f"Success rate: {(stats['successful'] / stats['total_requests'] * 100):.2f}%")
    print(f"Richieste al secondo: {stats['total_requests'] / total_elapsed:.2f} req/s")

    if stats['total_time'] > 0:
        print(f"Tempo medio risposta: {(stats['total_time'] / stats['total_requests']):.3f}s")

    print()

    if stats['failed'] > 0:
        print("⚠️ Errori rilevati:")
        # Mostra solo primi 10 errori unici
        unique_errors = list(set(stats['errors']))[:10]
        for error in unique_errors:
            print(f"  - {error}")
        if len(stats['errors']) > 10:
            print(f"  ... e altri {len(stats['errors']) - 10} errori")

    print("=" * 70)

    # Salva report JSON
    report = {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "base_url": BASE_URL,
            "num_threads": NUM_THREADS,
            "requests_per_thread": REQUESTS_PER_THREAD,
            "timeout": TIMEOUT
        },
        "results": {
            "total_time": total_elapsed,
            "total_requests": stats["total_requests"],
            "successful": stats["successful"],
            "failed": stats["failed"],
            "success_rate": stats["successful"] / stats["total_requests"] * 100 if stats["total_requests"] > 0 else 0,
            "requests_per_second": stats["total_requests"] / total_elapsed if total_elapsed > 0 else 0,
            "avg_response_time": stats["total_time"] / stats["total_requests"] if stats["total_requests"] > 0 else 0
        },
        "errors": stats["errors"][:50]  # Prime 50 errori
    }

    report_file = "../_fix_results/reports/stress_test_report.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\n📊 Report salvato in: {report_file}")

    # Exit code basato sul success rate
    if stats['successful'] / stats['total_requests'] >= 0.95:
        print("\n✅ STRESS TEST PASSED (success rate >= 95%)")
        sys.exit(0)
    else:
        print("\n❌ STRESS TEST FAILED (success rate < 95%)")
        sys.exit(1)

if __name__ == "__main__":
    main()
