"""
Sistema di monitoring e logging avanzato per performance e sicurezza
"""

import logging
import time
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from functools import wraps
from contextlib import contextmanager
import psutil
import asyncio
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import threading

# Configurazione logging strutturato
class StructuredLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)

        # Formatter per output strutturato
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # File handler per produzione
        if os.getenv('ENVIRONMENT') == 'production':
            file_handler = logging.FileHandler('app.log')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def info(self, message: str, extra: Optional[Dict] = None):
        self._log('info', message, extra)

    def warning(self, message: str, extra: Optional[Dict] = None):
        self._log('warning', message, extra)

    def error(self, message: str, extra: Optional[Dict] = None):
        self._log('error', message, extra)

    def critical(self, message: str, extra: Optional[Dict] = None):
        self._log('critical', message, extra)

    def _log(self, level: str, message: str, extra: Optional[Dict] = None):
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'message': message,
            'level': level
        }

        if extra:
            log_data.update(extra)

        getattr(self.logger, level)(json.dumps(log_data))

@dataclass
class PerformanceMetric:
    operation: str
    duration: float
    timestamp: datetime
    status: str
    user_id: Optional[int] = None
    endpoint: Optional[str] = None
    database_queries: int = 0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0

@dataclass
class SecurityEvent:
    event_type: str
    user_id: Optional[int]
    ip_address: str
    user_agent: str
    endpoint: str
    timestamp: datetime
    details: Dict[str, Any]
    severity: str = 'info'  # info, warning, critical

class MetricsCollector:
    """Collettore di metriche per performance monitoring"""

    def __init__(self):
        self.metrics: deque = deque(maxlen=10000)  # Keep last 10k metrics
        self.security_events: deque = deque(maxlen=5000)
        self.alerts: List[Dict] = []
        self.thresholds = {
            'response_time': 2.0,  # seconds
            'memory_usage': 80.0,  # percentage
            'cpu_usage': 80.0,     # percentage
            'error_rate': 5.0,     # percentage
            'failed_logins': 5     # count per 5 minutes
        }
        self._start_time = datetime.utcnow()
        self._request_counts = defaultdict(int)
        self._error_counts = defaultdict(int)
        self._failed_logins = deque(maxlen=100)

        # Background thread per cleanup
        self._cleanup_thread = threading.Thread(target=self._periodic_cleanup, daemon=True)
        self._cleanup_thread.start()

    def record_performance(self, metric: PerformanceMetric):
        """Registra metrica di performance"""
        self.metrics.append(metric)

        # Check alerts
        self._check_performance_alerts(metric)

    def record_security_event(self, event: SecurityEvent):
        """Registra evento di sicurezza"""
        self.security_events.append(event)

        # Track failed logins
        if event.event_type == 'login_failed':
            self._failed_logins.append(event.timestamp)

        # Check security alerts
        self._check_security_alerts(event)

    def get_performance_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Ottieni riassunto performance delle ultime ore"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent_metrics = [m for m in self.metrics if m.timestamp >= cutoff]

        if not recent_metrics:
            return {}

        # Calcola statistiche
        durations = [m.duration for m in recent_metrics]
        error_count = len([m for m in recent_metrics if m.status == 'error'])

        # Raggruppa per endpoint
        endpoint_stats = defaultdict(list)
        for metric in recent_metrics:
            if metric.endpoint:
                endpoint_stats[metric.endpoint].append(metric.duration)

        return {
            'total_requests': len(recent_metrics),
            'error_count': error_count,
            'error_rate': (error_count / len(recent_metrics)) * 100,
            'avg_response_time': sum(durations) / len(durations),
            'max_response_time': max(durations),
            'min_response_time': min(durations),
            'p95_response_time': self._percentile(durations, 95),
            'p99_response_time': self._percentile(durations, 99),
            'slowest_endpoints': self._get_slowest_endpoints(endpoint_stats),
            'system_metrics': self._get_system_metrics(),
            'alerts': self.alerts[-10:],  # Last 10 alerts
            'uptime_seconds': (datetime.utcnow() - self._start_time).total_seconds()
        }

    def get_security_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Ottieni riassunto sicurezza delle ultime ore"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent_events = [e for e in self.security_events if e.timestamp >= cutoff]

        # Raggruppa eventi per tipo
        event_types = defaultdict(int)
        severity_counts = defaultdict(int)
        ip_counts = defaultdict(int)

        for event in recent_events:
            event_types[event.event_type] += 1
            severity_counts[event.severity] += 1
            ip_counts[event.ip_address] += 1

        # Failed logins nelle ultime 5 minuti
        recent_fails = len([
            t for t in self._failed_logins
            if t >= datetime.utcnow() - timedelta(minutes=5)
        ])

        return {
            'total_events': len(recent_events),
            'event_types': dict(event_types),
            'severity_distribution': dict(severity_counts),
            'suspicious_ips': {
                ip: count for ip, count in ip_counts.items()
                if count > 10  # More than 10 events
            },
            'failed_logins_5min': recent_fails,
            'critical_alerts': [
                a for a in self.alerts
                if a.get('severity') == 'critical' and
                a.get('timestamp', datetime.min) >= cutoff
            ]
        }

    def _check_performance_alerts(self, metric: PerformanceMetric):
        """Controlla se generare alert di performance"""
        alerts = []

        # Response time alert
        if metric.duration > self.thresholds['response_time']:
            alerts.append({
                'type': 'slow_response',
                'severity': 'warning',
                'message': f'Slow response: {metric.duration:.2f}s on {metric.endpoint}',
                'metric': asdict(metric),
                'timestamp': datetime.utcnow()
            })

        # Memory usage alert
        if metric.memory_usage > self.thresholds['memory_usage']:
            alerts.append({
                'type': 'high_memory',
                'severity': 'critical',
                'message': f'High memory usage: {metric.memory_usage:.1f}%',
                'metric': asdict(metric),
                'timestamp': datetime.utcnow()
            })

        # CPU usage alert
        if metric.cpu_usage > self.thresholds['cpu_usage']:
            alerts.append({
                'type': 'high_cpu',
                'severity': 'warning',
                'message': f'High CPU usage: {metric.cpu_usage:.1f}%',
                'metric': asdict(metric),
                'timestamp': datetime.utcnow()
            })

        self.alerts.extend(alerts)

    def _check_security_alerts(self, event: SecurityEvent):
        """Controlla se generare alert di sicurezza"""
        alerts = []

        # Failed login attempts
        recent_fails = len([
            t for t in self._failed_logins
            if t >= datetime.utcnow() - timedelta(minutes=5)
        ])

        if recent_fails >= self.thresholds['failed_logins']:
            alerts.append({
                'type': 'brute_force_attempt',
                'severity': 'critical',
                'message': f'Multiple failed logins: {recent_fails} in 5 minutes',
                'event': asdict(event),
                'timestamp': datetime.utcnow()
            })

        # Critical security events
        if event.severity == 'critical':
            alerts.append({
                'type': 'critical_security_event',
                'severity': 'critical',
                'message': f'Critical security event: {event.event_type}',
                'event': asdict(event),
                'timestamp': datetime.utcnow()
            })

        self.alerts.extend(alerts)

    def _get_system_metrics(self) -> Dict[str, float]:
        """Ottieni metriche di sistema"""
        try:
            return {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent,
                'load_average': os.getloadavg()[0] if hasattr(os, 'getloadavg') else 0.0
            }
        except Exception:
            return {}

    def _get_slowest_endpoints(self, endpoint_stats: Dict, limit: int = 5) -> List[Dict]:
        """Ottieni gli endpoint più lenti"""
        endpoint_avgs = []
        for endpoint, durations in endpoint_stats.items():
            avg_duration = sum(durations) / len(durations)
            endpoint_avgs.append({
                'endpoint': endpoint,
                'avg_duration': avg_duration,
                'request_count': len(durations),
                'max_duration': max(durations)
            })

        return sorted(endpoint_avgs, key=lambda x: x['avg_duration'], reverse=True)[:limit]

    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calcola percentile"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data)) - 1
        return sorted_data[max(0, index)]

    def _periodic_cleanup(self):
        """Cleanup periodico dei dati vecchi"""
        while True:
            try:
                # Rimuovi alert vecchi (più di 24 ore)
                cutoff = datetime.utcnow() - timedelta(hours=24)
                self.alerts = [
                    alert for alert in self.alerts
                    if alert.get('timestamp', datetime.min) >= cutoff
                ]

                # Rimuovi failed logins vecchi
                self._failed_logins = deque([
                    timestamp for timestamp in self._failed_logins
                    if timestamp >= datetime.utcnow() - timedelta(hours=1)
                ], maxlen=100)

                time.sleep(3600)  # Cleanup ogni ora
            except Exception as e:
                logging.error(f"Error in periodic cleanup: {e}")
                time.sleep(3600)

# Istanza globale
metrics_collector = MetricsCollector()
logger = StructuredLogger('gestionale')

# Decoratori per monitoring automatico
def monitor_performance(operation: str = None):
    """Decorator per monitorare performance di una funzione"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            start_memory = psutil.Process().memory_percent()
            start_cpu = psutil.cpu_percent()

            try:
                result = await func(*args, **kwargs)
                status = 'success'
                return result
            except Exception as e:
                status = 'error'
                logger.error(f"Error in {operation or func.__name__}", {
                    'function': func.__name__,
                    'error': str(e),
                    'args': str(args)[:100],  # Limit size
                })
                raise
            finally:
                duration = time.time() - start_time
                end_memory = psutil.Process().memory_percent()
                end_cpu = psutil.cpu_percent()

                metric = PerformanceMetric(
                    operation=operation or func.__name__,
                    duration=duration,
                    timestamp=datetime.utcnow(),
                    status=status,
                    memory_usage=end_memory,
                    cpu_usage=end_cpu
                )

                metrics_collector.record_performance(metric)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            start_memory = psutil.Process().memory_percent()

            try:
                result = func(*args, **kwargs)
                status = 'success'
                return result
            except Exception as e:
                status = 'error'
                logger.error(f"Error in {operation or func.__name__}", {
                    'function': func.__name__,
                    'error': str(e),
                    'args': str(args)[:100],
                })
                raise
            finally:
                duration = time.time() - start_time
                end_memory = psutil.Process().memory_percent()

                metric = PerformanceMetric(
                    operation=operation or func.__name__,
                    duration=duration,
                    timestamp=datetime.utcnow(),
                    status=status,
                    memory_usage=end_memory,
                    cpu_usage=0.0
                )

                metrics_collector.record_performance(metric)

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

@contextmanager
def monitor_database_query(query_type: str = "unknown"):
    """Context manager per monitorare query database"""
    start_time = time.time()

    try:
        yield
    finally:
        duration = time.time() - start_time

        if duration > 1.0:  # Log only slow queries
            logger.warning("Slow database query", {
                'query_type': query_type,
                'duration': duration,
                'threshold': 1.0
            })

def log_security_event(
    event_type: str,
    user_id: Optional[int],
    ip_address: str,
    user_agent: str,
    endpoint: str,
    details: Dict[str, Any],
    severity: str = 'info'
):
    """Log evento di sicurezza"""
    event = SecurityEvent(
        event_type=event_type,
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        endpoint=endpoint,
        timestamp=datetime.utcnow(),
        details=details,
        severity=severity
    )

    metrics_collector.record_security_event(event)

    logger.info(f"Security event: {event_type}", {
        'event': asdict(event)
    })

# Health check functions
def get_health_status() -> Dict[str, Any]:
    """Ottieni stato di salute dell'applicazione"""
    try:
        system_metrics = metrics_collector._get_system_metrics()

        # Determina stato generale
        status = 'healthy'
        issues = []

        if system_metrics.get('memory_percent', 0) > 90:
            status = 'degraded'
            issues.append('High memory usage')

        if system_metrics.get('cpu_percent', 0) > 90:
            status = 'degraded'
            issues.append('High CPU usage')

        # Controlla alert critici recenti
        critical_alerts = [
            a for a in metrics_collector.alerts[-10:]
            if a.get('severity') == 'critical' and
            a.get('timestamp', datetime.min) >= datetime.utcnow() - timedelta(minutes=5)
        ]

        if critical_alerts:
            status = 'unhealthy'
            issues.extend([a['message'] for a in critical_alerts])

        return {
            'status': status,
            'timestamp': datetime.utcnow().isoformat(),
            'uptime_seconds': (datetime.utcnow() - metrics_collector._start_time).total_seconds(),
            'system_metrics': system_metrics,
            'issues': issues,
            'version': '2.0.0'
        }

    except Exception as e:
        logger.error("Error getting health status", {'error': str(e)})
        return {
            'status': 'unhealthy',
            'timestamp': datetime.utcnow().isoformat(),
            'error': str(e),
            'version': '2.0.0'
        }