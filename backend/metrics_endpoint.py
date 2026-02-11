# =================================================================
# FILE: metrics_endpoint.py
# =================================================================
# SCOPO: Esporre metriche applicazione per Prometheus
#
# Usa prometheus-fastapi-instrumentator per instrumentare FastAPI
# e esporre metriche automaticamente su /metrics endpoint.
#
# METRICHE ESPOSTE:
# - http_requests_total: Contatore richieste per endpoint/metodo/status
# - http_request_duration_seconds: Latenza richieste (histogram)
# - http_requests_in_progress: Richieste concorrenti in corso
# - process_*: Metriche processo (CPU, memory, threads)
# - python_*: Metriche Python runtime (garbage collection, etc.)
# =================================================================

from prometheus_fastapi_instrumentator import Instrumentator, metrics
from prometheus_client import Counter, Histogram, Gauge, Info
from fastapi import FastAPI, Request
import time
import psutil
import os

# =================================================================
# METRICHE CUSTOM
# =================================================================
# Oltre alle metriche standard, definiamo metriche custom
# specifiche per il nostro gestionale
# =================================================================

# Contatore: Numero collaboratori creati
collaborators_created_total = Counter(
    'collaborators_created_total',
    'Total number of collaborators created',
    ['status']  # Label: success/failure
)

# Contatore: Numero progetti creati
projects_created_total = Counter(
    'projects_created_total',
    'Total number of projects created',
    ['status']
)

# Contatore: Numero presenze registrate
attendances_created_total = Counter(
    'attendances_created_total',
    'Total number of attendances recorded',
    ['status']
)

# Gauge: Numero attuale collaboratori attivi nel sistema
active_collaborators_gauge = Gauge(
    'active_collaborators_current',
    'Current number of active collaborators in system'
)

# Gauge: Numero attuale progetti attivi
active_projects_gauge = Gauge(
    'active_projects_current',
    'Current number of active projects'
)

# Histogram: Durata operazioni database
db_operation_duration = Histogram(
    'db_operation_duration_seconds',
    'Duration of database operations',
    ['operation', 'table'],  # Labels: operation type e tabella
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]
)

# Info: Informazioni applicazione
app_info = Info('gestionale_app', 'Gestionale application information')
app_info.info({
    'version': '3.2',
    'python_version': f"{os.sys.version_info.major}.{os.sys.version_info.minor}",
    'environment': os.getenv('ENVIRONMENT', 'development')
})


# =================================================================
# METRICHE SISTEMA
# =================================================================

# Gauge: CPU usage dell'applicazione
app_cpu_usage = Gauge(
    'app_cpu_usage_percent',
    'Application CPU usage percentage'
)

# Gauge: Memory usage dell'applicazione
app_memory_usage = Gauge(
    'app_memory_usage_bytes',
    'Application memory usage in bytes'
)

# Funzione per aggiornare metriche sistema
def update_system_metrics():
    """
    Aggiorna metriche sistema (CPU, memory).

    Chiamata periodicamente da background task.
    """
    process = psutil.Process()

    # CPU usage
    app_cpu_usage.set(process.cpu_percent(interval=0.1))

    # Memory usage
    memory_info = process.memory_info()
    app_memory_usage.set(memory_info.rss)  # Resident Set Size


# =================================================================
# SETUP INSTRUMENTATOR
# =================================================================

def setup_metrics(app: FastAPI):
    """
    Configura instrumentazione Prometheus per FastAPI app.

    PARAMETRI:
        app: FastAPI application instance

    EFFETTI:
        - Aggiunge middleware per tracciare richieste HTTP
        - Espone endpoint /metrics con metriche Prometheus
        - Registra metriche custom

    CHIAMARE in main.py:
        from metrics_endpoint import setup_metrics
        setup_metrics(app)
    """

    # Crea instrumentator
    instrumentator = Instrumentator(
        # Include o escludi certi path
        should_group_status_codes=True,  # Raggruppa 2xx, 3xx, 4xx, 5xx
        should_ignore_untemplated=False,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/metrics", "/health"],  # Non tracciare questi
        env_var_name="ENABLE_METRICS",
        inprogress_name="http_requests_inprogress",
        inprogress_labels=True,
    )

    # Aggiungi metriche standard
    instrumentator.add(
        metrics.request_size(
            should_include_handler=True,
            should_include_method=True,
            should_include_status=True,
        )
    )

    instrumentator.add(
        metrics.response_size(
            should_include_handler=True,
            should_include_method=True,
            should_include_status=True,
        )
    )

    instrumentator.add(
        metrics.latency(
            should_include_handler=True,
            should_include_method=True,
            should_include_status=True,
        )
    )

    instrumentator.add(
        metrics.requests(
            should_include_handler=True,
            should_include_method=True,
            should_include_status=True,
        )
    )

    # Instrumenta app
    instrumentator.instrument(app)

    # Esponi endpoint /metrics
    instrumentator.expose(app, endpoint="/metrics", include_in_schema=False)

    # Background task per metriche sistema (opzionale)
    @app.on_event("startup")
    async def startup_metrics():
        """Inizializza metriche al startup"""
        update_system_metrics()

    return instrumentator


# =================================================================
# HELPER FUNCTIONS PER USARE METRICHE CUSTOM
# =================================================================

def record_collaborator_created(success: bool = True):
    """
    Registra creazione collaboratore nelle metriche.

    USO in crud.py o endpoint:
        from metrics_endpoint import record_collaborator_created
        record_collaborator_created(success=True)
    """
    status = "success" if success else "failure"
    collaborators_created_total.labels(status=status).inc()


def record_project_created(success: bool = True):
    """Registra creazione progetto"""
    status = "success" if success else "failure"
    projects_created_total.labels(status=status).inc()


def record_attendance_created(success: bool = True):
    """Registra presenza"""
    status = "success" if success else "failure"
    attendances_created_total.labels(status=status).inc()


def update_active_counts(collaborators: int, projects: int):
    """
    Aggiorna gauge con contatori attuali.

    CHIAMARE periodicamente o dopo operazioni CRUD:
        update_active_counts(
            collaborators=db.query(Collaborator).count(),
            projects=db.query(Project).filter(Project.status=='active').count()
        )
    """
    active_collaborators_gauge.set(collaborators)
    active_projects_gauge.set(projects)


def track_db_operation(operation: str, table: str):
    """
    Context manager per tracciare durata operazioni DB.

    USO:
        with track_db_operation('select', 'collaborators'):
            results = db.query(Collaborator).all()
    """
    class DBOperationTracker:
        def __enter__(self):
            self.start_time = time.time()
            return self

        def __exit__(self, *args):
            duration = time.time() - self.start_time
            db_operation_duration.labels(
                operation=operation,
                table=table
            ).observe(duration)

    return DBOperationTracker()


# =================================================================
# ESEMPI USO
# =================================================================
"""
# In main.py - Setup iniziale:
from metrics_endpoint import setup_metrics
setup_metrics(app)

# In crud.py - Registra operazioni:
from metrics_endpoint import (
    record_collaborator_created,
    track_db_operation,
    update_active_counts
)

def create_collaborator(db, collaborator):
    try:
        with track_db_operation('insert', 'collaborators'):
            db_collaborator = Collaborator(**collaborator.dict())
            db.add(db_collaborator)
            db.commit()

        record_collaborator_created(success=True)

        # Aggiorna contatori
        total = db.query(Collaborator).count()
        update_active_counts(collaborators=total, projects=0)

        return db_collaborator

    except Exception as e:
        record_collaborator_created(success=False)
        raise

# In endpoint - Tracking manuale:
@app.post("/collaborators/")
def create_collaborator_endpoint(...):
    start = time.time()
    try:
        result = crud.create_collaborator(db, collaborator)
        return result
    finally:
        duration = time.time() - start
        logger.info(f"Collaborator created in {duration:.3f}s")
"""


# =================================================================
# QUERY PROMQL UTILI
# =================================================================
"""
# Rate creazione collaboratori (ultimi 5min)
rate(collaborators_created_total{status="success"}[5m])

# Success rate creazione collaboratori
rate(collaborators_created_total{status="success"}[5m]) /
rate(collaborators_created_total[5m]) * 100

# P95 latency operazioni database
histogram_quantile(0.95, rate(db_operation_duration_seconds_bucket[5m]))

# Numero richieste HTTP per endpoint
sum by (handler) (rate(http_requests_total[5m]))

# Error rate API
rate(http_requests_total{status=~"5.."}[5m])

# Memory usage trend
app_memory_usage_bytes / 1024 / 1024  # In MB

# CPU usage
avg_over_time(app_cpu_usage_percent[5m])
"""
