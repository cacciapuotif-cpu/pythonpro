# Sistema di monitoraggio performance in tempo reale
import time
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import deque, defaultdict
import logging
from dataclasses import dataclass, asdict
import json
from functools import wraps

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Metriche di performance del sistema"""
    timestamp: str
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_usage_percent: float
    active_connections: int
    response_time_avg: float
    requests_per_minute: int
    error_rate: float
    uptime_seconds: int

@dataclass
class EndpointMetrics:
    """Metriche specifiche per endpoint"""
    endpoint: str
    method: str
    total_requests: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    error_count: int
    last_request: str

class PerformanceMonitor:
    """Monitora performance del sistema in tempo reale"""

    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.metrics_history: deque = deque(maxlen=max_history)
        self.endpoint_metrics: Dict[str, EndpointMetrics] = {}
        self.response_times: deque = deque(maxlen=100)  # Ultimi 100 response times
        self.requests_minute: deque = deque(maxlen=60)  # Requests per minuto
        self.error_count = 0
        self.total_requests = 0
        self.start_time = datetime.now()
        self.is_monitoring = False
        self.monitor_thread = None
        self.lock = threading.Lock()

        # Inizializza contatori per minuto
        for _ in range(60):
            self.requests_minute.append(0)

    def start_monitoring(self, interval: int = 30):
        """Avvia il monitoraggio automatico"""
        if self.is_monitoring:
            return

        self.is_monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True
        )
        self.monitor_thread.start()
        logger.info(f"Performance monitoring started (interval: {interval}s)")

    def stop_monitoring(self):
        """Ferma il monitoraggio"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Performance monitoring stopped")

    def _monitor_loop(self, interval: int):
        """Loop principale di monitoraggio"""
        while self.is_monitoring:
            try:
                metrics = self._collect_system_metrics()
                with self.lock:
                    self.metrics_history.append(metrics)

                # Aggiorna contatori requests per minuto
                current_minute = datetime.now().minute
                if len(self.requests_minute) > current_minute:
                    self.requests_minute[current_minute] = 0

                time.sleep(interval)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

    def _collect_system_metrics(self) -> PerformanceMetrics:
        """Raccoglie metriche di sistema"""
        try:
            # CPU e memoria
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            # Connessioni di rete (approssimazione)
            active_connections = len(psutil.net_connections())

            # Metriche applicazione
            avg_response_time = (
                sum(self.response_times) / len(self.response_times)
                if self.response_times else 0
            )

            requests_per_minute = sum(self.requests_minute)
            error_rate = (
                (self.error_count / self.total_requests * 100)
                if self.total_requests > 0 else 0
            )

            uptime = (datetime.now() - self.start_time).total_seconds()

            return PerformanceMetrics(
                timestamp=datetime.now().isoformat(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=memory.used / (1024 * 1024),
                disk_usage_percent=disk.percent,
                active_connections=active_connections,
                response_time_avg=avg_response_time,
                requests_per_minute=requests_per_minute,
                error_rate=error_rate,
                uptime_seconds=int(uptime)
            )

        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return PerformanceMetrics(
                timestamp=datetime.now().isoformat(),
                cpu_percent=0, memory_percent=0, memory_used_mb=0,
                disk_usage_percent=0, active_connections=0,
                response_time_avg=0, requests_per_minute=0,
                error_rate=0, uptime_seconds=0
            )

    def record_request(self, endpoint: str, method: str, response_time: float, status_code: int):
        """Registra metriche di una richiesta"""
        with self.lock:
            self.total_requests += 1

            # Aggiorna response times
            self.response_times.append(response_time)

            # Aggiorna contatore errori
            if status_code >= 400:
                self.error_count += 1

            # Aggiorna requests per minuto
            current_minute = datetime.now().minute
            if len(self.requests_minute) > current_minute:
                self.requests_minute[current_minute] += 1

            # Aggiorna metriche endpoint
            endpoint_key = f"{method} {endpoint}"
            if endpoint_key not in self.endpoint_metrics:
                self.endpoint_metrics[endpoint_key] = EndpointMetrics(
                    endpoint=endpoint,
                    method=method,
                    total_requests=0,
                    avg_response_time=0,
                    min_response_time=float('inf'),
                    max_response_time=0,
                    error_count=0,
                    last_request=datetime.now().isoformat()
                )

            metrics = self.endpoint_metrics[endpoint_key]
            metrics.total_requests += 1
            metrics.last_request = datetime.now().isoformat()

            # Aggiorna response times
            if response_time < metrics.min_response_time:
                metrics.min_response_time = response_time
            if response_time > metrics.max_response_time:
                metrics.max_response_time = response_time

            # Calcola nuova media (weighted average)
            metrics.avg_response_time = (
                (metrics.avg_response_time * (metrics.total_requests - 1) + response_time)
                / metrics.total_requests
            )

            if status_code >= 400:
                metrics.error_count += 1

    def get_current_metrics(self) -> Dict[str, Any]:
        """Ottieni metriche correnti"""
        with self.lock:
            current = self._collect_system_metrics()
            return {
                "current": asdict(current),
                "trends": self._calculate_trends(),
                "alerts": self._check_alerts(current)
            }

    def get_endpoint_metrics(self) -> List[Dict[str, Any]]:
        """Ottieni metriche per endpoint"""
        with self.lock:
            return [asdict(metrics) for metrics in self.endpoint_metrics.values()]

    def get_historical_metrics(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Ottieni metriche storiche"""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        with self.lock:
            filtered_metrics = [
                asdict(metrics) for metrics in self.metrics_history
                if datetime.fromisoformat(metrics.timestamp) >= cutoff_time
            ]

        return filtered_metrics

    def _calculate_trends(self) -> Dict[str, str]:
        """Calcola trend delle metriche principali"""
        if len(self.metrics_history) < 2:
            return {}

        recent = list(self.metrics_history)[-10:]  # Ultimi 10 punti
        if len(recent) < 2:
            return {}

        trends = {}

        # Trend CPU
        cpu_values = [m.cpu_percent for m in recent]
        trends['cpu'] = 'increasing' if cpu_values[-1] > cpu_values[0] else 'decreasing'

        # Trend memoria
        memory_values = [m.memory_percent for m in recent]
        trends['memory'] = 'increasing' if memory_values[-1] > memory_values[0] else 'decreasing'

        # Trend response time
        response_values = [m.response_time_avg for m in recent if m.response_time_avg > 0]
        if response_values:
            trends['response_time'] = 'increasing' if response_values[-1] > response_values[0] else 'decreasing'

        return trends

    def _check_alerts(self, metrics: PerformanceMetrics) -> List[Dict[str, Any]]:
        """Controlla condizioni di alert"""
        alerts = []

        # Alert CPU alto
        if metrics.cpu_percent > 80:
            alerts.append({
                "type": "high_cpu",
                "severity": "critical" if metrics.cpu_percent > 90 else "warning",
                "message": f"CPU usage: {metrics.cpu_percent:.1f}%",
                "threshold": 80
            })

        # Alert memoria alta
        if metrics.memory_percent > 80:
            alerts.append({
                "type": "high_memory",
                "severity": "critical" if metrics.memory_percent > 90 else "warning",
                "message": f"Memory usage: {metrics.memory_percent:.1f}%",
                "threshold": 80
            })

        # Alert response time alto
        if metrics.response_time_avg > 2000:  # 2 secondi
            alerts.append({
                "type": "slow_response",
                "severity": "critical" if metrics.response_time_avg > 5000 else "warning",
                "message": f"Avg response time: {metrics.response_time_avg:.0f}ms",
                "threshold": 2000
            })

        # Alert tasso errori alto
        if metrics.error_rate > 5:  # 5%
            alerts.append({
                "type": "high_error_rate",
                "severity": "critical" if metrics.error_rate > 10 else "warning",
                "message": f"Error rate: {metrics.error_rate:.1f}%",
                "threshold": 5
            })

        return alerts

    def get_performance_summary(self) -> Dict[str, Any]:
        """Ottieni riassunto performance"""
        with self.lock:
            if not self.metrics_history:
                return {"status": "no_data"}

            recent_metrics = list(self.metrics_history)[-10:]  # Ultimi 10 punti

            avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
            avg_memory = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)
            avg_response = sum(m.response_time_avg for m in recent_metrics) / len(recent_metrics)

            # Determina stato generale
            status = "healthy"
            if avg_cpu > 80 or avg_memory > 80 or avg_response > 2000:
                status = "critical"
            elif avg_cpu > 60 or avg_memory > 60 or avg_response > 1000:
                status = "warning"

            return {
                "status": status,
                "avg_cpu_percent": round(avg_cpu, 1),
                "avg_memory_percent": round(avg_memory, 1),
                "avg_response_time_ms": round(avg_response, 0),
                "total_requests": self.total_requests,
                "total_errors": self.error_count,
                "uptime_hours": round((datetime.now() - self.start_time).total_seconds() / 3600, 1),
                "monitored_endpoints": len(self.endpoint_metrics)
            }

    def export_metrics(self, filepath: str, hours: int = 24):
        """Esporta metriche in formato JSON"""
        try:
            data = {
                "export_timestamp": datetime.now().isoformat(),
                "summary": self.get_performance_summary(),
                "historical_metrics": self.get_historical_metrics(hours),
                "endpoint_metrics": self.get_endpoint_metrics()
            }

            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Metrics exported to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Error exporting metrics: {e}")
            return False

# Decorator per misurare performance di endpoint
def monitor_performance(monitor: PerformanceMonitor):
    """Decorator per monitorare performance endpoint"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            status_code = 200

            try:
                response = await func(*args, **kwargs)
                return response
            except Exception as e:
                status_code = getattr(e, 'status_code', 500)
                raise
            finally:
                response_time = (time.time() - start_time) * 1000  # ms
                endpoint = getattr(func, '__name__', 'unknown')
                monitor.record_request(endpoint, 'AUTO', response_time, status_code)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            status_code = 200

            try:
                response = func(*args, **kwargs)
                return response
            except Exception as e:
                status_code = getattr(e, 'status_code', 500)
                raise
            finally:
                response_time = (time.time() - start_time) * 1000  # ms
                endpoint = getattr(func, '__name__', 'unknown')
                monitor.record_request(endpoint, 'AUTO', response_time, status_code)

        # Determina se la funzione è async
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator

# Singleton per il monitoraggio globale
performance_monitor = PerformanceMonitor()

def get_performance_monitor() -> PerformanceMonitor:
    """Ottieni istanza singleton del monitor"""
    return performance_monitor