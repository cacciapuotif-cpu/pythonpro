"""
Sistema di caching avanzato con Redis e fallback in-memory
Implementa cache distribuito, invalidazione intelligente e compressione
"""

import json
import pickle
import gzip
import hashlib
import time
from typing import Any, Optional, Dict, List, Callable, Union
from functools import wraps
from datetime import datetime, timedelta
import logging
import os
from dataclasses import dataclass

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    data: Any
    created_at: float
    expires_at: Optional[float]
    access_count: int = 0
    last_accessed: float = 0.0
    compressed: bool = False
    size_bytes: int = 0

class CacheManager:
    """Manager cache avanzato con supporto Redis e fallback in-memory"""

    def __init__(self, redis_url: Optional[str] = None, default_ttl: int = 3600):
        self.default_ttl = default_ttl
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'size_bytes': 0
        }

        # Configurazione Redis
        self.redis_client = None
        if REDIS_AVAILABLE and redis_url:
            try:
                self.redis_client = redis.from_url(
                    redis_url,
                    decode_responses=False,  # Per supportare dati binari
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    max_connections=20
                )
                # Test connessione
                self.redis_client.ping()
                logger.info("Redis cache initialized successfully")
            except Exception as e:
                logger.warning(f"Redis connection failed, using in-memory cache: {e}")
                self.redis_client = None

        # Fallback cache in-memory
        self._memory_cache: Dict[str, CacheEntry] = {}
        self._max_memory_items = 1000
        self._compression_threshold = 1024  # 1KB

    def get(self, key: str) -> Optional[Any]:
        """Ottieni valore dalla cache"""
        cache_key = self._make_key(key)

        try:
            if self.redis_client:
                return self._get_from_redis(cache_key)
            else:
                return self._get_from_memory(cache_key)
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Imposta valore in cache"""
        cache_key = self._make_key(key)
        ttl = ttl or self.default_ttl

        try:
            if self.redis_client:
                return self._set_to_redis(cache_key, value, ttl)
            else:
                return self._set_to_memory(cache_key, value, ttl)
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Rimuovi valore dalla cache"""
        cache_key = self._make_key(key)

        try:
            if self.redis_client:
                result = self.redis_client.delete(cache_key) > 0
            else:
                result = cache_key in self._memory_cache
                if result:
                    del self._memory_cache[cache_key]

            if result:
                self.stats['deletes'] += 1

            return result
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False

    def clear(self, pattern: Optional[str] = None) -> int:
        """Pulisci cache (opzionalmente con pattern)"""
        try:
            if self.redis_client:
                if pattern:
                    keys = self.redis_client.keys(f"gestionale:{pattern}*")
                    if keys:
                        return self.redis_client.delete(*keys)
                    return 0
                else:
                    return self.redis_client.flushdb()
            else:
                if pattern:
                    prefix = f"gestionale:{pattern}"
                    keys_to_delete = [k for k in self._memory_cache.keys() if k.startswith(prefix)]
                    for key in keys_to_delete:
                        del self._memory_cache[key]
                    return len(keys_to_delete)
                else:
                    count = len(self._memory_cache)
                    self._memory_cache.clear()
                    return count
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """Ottieni statistiche cache"""
        hit_rate = 0.0
        total_requests = self.stats['hits'] + self.stats['misses']
        if total_requests > 0:
            hit_rate = self.stats['hits'] / total_requests

        memory_stats = {}
        if not self.redis_client:
            memory_stats = {
                'items_count': len(self._memory_cache),
                'memory_usage_bytes': sum(
                    entry.size_bytes for entry in self._memory_cache.values()
                )
            }

        return {
            'backend': 'redis' if self.redis_client else 'memory',
            'hit_rate': hit_rate,
            'total_requests': total_requests,
            **self.stats,
            **memory_stats
        }

    def _make_key(self, key: str) -> str:
        """Crea chiave cache con namespace"""
        return f"gestionale:{key}"

    def _get_from_redis(self, cache_key: str) -> Optional[Any]:
        """Ottieni da Redis"""
        data = self.redis_client.get(cache_key)
        if data is None:
            self.stats['misses'] += 1
            return None

        self.stats['hits'] += 1

        try:
            # Decomprimi se necessario
            if data.startswith(b'GZIP:'):
                data = gzip.decompress(data[5:])

            # Deserializza
            return pickle.loads(data)
        except Exception as e:
            logger.error(f"Error deserializing Redis data: {e}")
            return None

    def _set_to_redis(self, cache_key: str, value: Any, ttl: int) -> bool:
        """Imposta in Redis"""
        try:
            # Serializza
            data = pickle.dumps(value)

            # Comprimi se grande
            if len(data) > self._compression_threshold:
                compressed_data = gzip.compress(data)
                if len(compressed_data) < len(data):
                    data = b'GZIP:' + compressed_data

            # Imposta con TTL
            result = self.redis_client.setex(cache_key, ttl, data)
            if result:
                self.stats['sets'] += 1

            return result
        except Exception as e:
            logger.error(f"Error setting Redis data: {e}")
            return False

    def _get_from_memory(self, cache_key: str) -> Optional[Any]:
        """Ottieni da cache in-memory"""
        if cache_key not in self._memory_cache:
            self.stats['misses'] += 1
            return None

        entry = self._memory_cache[cache_key]

        # Controlla scadenza
        now = time.time()
        if entry.expires_at and now > entry.expires_at:
            del self._memory_cache[cache_key]
            self.stats['misses'] += 1
            return None

        # Aggiorna statistiche accesso
        entry.access_count += 1
        entry.last_accessed = now
        self.stats['hits'] += 1

        return entry.data

    def _set_to_memory(self, cache_key: str, value: Any, ttl: int) -> bool:
        """Imposta in cache in-memory"""
        try:
            # Controlla limite memoria
            if len(self._memory_cache) >= self._max_memory_items:
                self._evict_lru()

            # Calcola dimensione
            data_size = len(pickle.dumps(value))

            # Crea entry
            expires_at = time.time() + ttl if ttl > 0 else None
            entry = CacheEntry(
                data=value,
                created_at=time.time(),
                expires_at=expires_at,
                size_bytes=data_size
            )

            self._memory_cache[cache_key] = entry
            self.stats['sets'] += 1
            self.stats['size_bytes'] += data_size

            return True
        except Exception as e:
            logger.error(f"Error setting memory data: {e}")
            return False

    def _evict_lru(self) -> None:
        """Rimuovi elemento meno usato di recente"""
        if not self._memory_cache:
            return

        # Trova chiave meno acceduta
        lru_key = min(
            self._memory_cache.keys(),
            key=lambda k: (
                self._memory_cache[k].access_count,
                self._memory_cache[k].last_accessed
            )
        )

        entry = self._memory_cache[lru_key]
        self.stats['size_bytes'] -= entry.size_bytes
        del self._memory_cache[lru_key]

# Istanza globale
def _build_redis_url() -> str:
    """Costruisce REDIS_URL da variabili componenti se non fornita direttamente."""
    if os.getenv('REDIS_URL'):
        return os.getenv('REDIS_URL')
    host = os.getenv('REDIS_HOST', 'localhost')
    port = os.getenv('REDIS_PORT', '6379')
    password = os.getenv('REDIS_PASSWORD')
    if password:
        return f"redis://:{password}@{host}:{port}/0"
    return f"redis://{host}:{port}/0"

cache_manager = CacheManager(
    redis_url=_build_redis_url(),
    default_ttl=int(os.getenv('CACHE_TTL', '3600'))
)

# Decoratori per caching automatico
def cached(
    key_func: Optional[Callable] = None,
    ttl: Optional[int] = None,
    invalidate_on: Optional[List[str]] = None
):
    """
    Decorator per caching automatico delle funzioni

    Args:
        key_func: Funzione per generare chiave cache
        ttl: Time to live in secondi
        invalidate_on: Lista di eventi che invalidano la cache
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Genera chiave cache
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = _default_key_func(func, *args, **kwargs)

            # Prova a ottenere dalla cache
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Esegui funzione
            result = func(*args, **kwargs)

            # Salva in cache
            cache_manager.set(cache_key, result, ttl)

            return result

        # Aggiungi metodo per invalidazione manuale
        wrapper.invalidate = lambda *args, **kwargs: cache_manager.delete(
            key_func(*args, **kwargs) if key_func else _default_key_func(func, *args, **kwargs)
        )

        # Aggiungi metodo per flush pattern
        wrapper.flush_pattern = lambda pattern: cache_manager.clear(pattern)

        return wrapper
    return decorator

def cache_result(ttl: int = 3600, key_prefix: str = None):
    """Decorator semplificato per caching risultati"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Genera chiave
            prefix = key_prefix or func.__name__
            key_parts = [prefix]

            # Aggiungi args
            for arg in args:
                if isinstance(arg, (str, int, float, bool)):
                    key_parts.append(str(arg))

            # Aggiungi kwargs
            for k, v in sorted(kwargs.items()):
                if isinstance(v, (str, int, float, bool)):
                    key_parts.append(f"{k}:{v}")

            cache_key = ":".join(key_parts)

            # Cerca in cache
            result = cache_manager.get(cache_key)
            if result is not None:
                return result

            # Esegui e salva
            result = func(*args, **kwargs)
            cache_manager.set(cache_key, result, ttl)

            return result

        return wrapper
    return decorator

def invalidate_cache_pattern(pattern: str):
    """Invalida cache con pattern specifico"""
    return cache_manager.clear(pattern)

def _default_key_func(func, *args, **kwargs) -> str:
    """Genera chiave cache di default"""
    key_parts = [func.__name__]

    # Hash degli argomenti per chiave univoca
    args_str = str(args) + str(sorted(kwargs.items()))
    args_hash = hashlib.md5(args_str.encode()).hexdigest()[:12]
    key_parts.append(args_hash)

    return ":".join(key_parts)

# Cache specifiche per entità
class EntityCache:
    """Cache specializzata per entità del database"""

    def __init__(self, entity_name: str, ttl: int = 1800):
        self.entity_name = entity_name
        self.ttl = ttl

    def get_list(self, filters: Dict = None, pagination: Dict = None) -> Optional[List]:
        """Cache per liste di entità"""
        key = f"{self.entity_name}:list:{self._hash_params(filters, pagination)}"
        return cache_manager.get(key)

    def set_list(self, data: List, filters: Dict = None, pagination: Dict = None) -> bool:
        """Salva lista in cache"""
        key = f"{self.entity_name}:list:{self._hash_params(filters, pagination)}"
        return cache_manager.set(key, data, self.ttl)

    def get_item(self, item_id: Union[int, str]) -> Optional[Dict]:
        """Cache per singola entità"""
        key = f"{self.entity_name}:item:{item_id}"
        return cache_manager.get(key)

    def set_item(self, item_id: Union[int, str], data: Dict) -> bool:
        """Salva entità in cache"""
        key = f"{self.entity_name}:item:{item_id}"
        return cache_manager.set(key, data, self.ttl)

    def invalidate_item(self, item_id: Union[int, str]) -> bool:
        """Invalida cache di una entità"""
        key = f"{self.entity_name}:item:{item_id}"
        return cache_manager.delete(key)

    def invalidate_all(self) -> int:
        """Invalida tutta la cache dell'entità"""
        return cache_manager.clear(self.entity_name)

    def _hash_params(self, filters: Dict = None, pagination: Dict = None) -> str:
        """Hash parametri per chiave univoca"""
        params = {
            'filters': filters or {},
            'pagination': pagination or {}
        }
        params_str = json.dumps(params, sort_keys=True)
        return hashlib.md5(params_str.encode()).hexdigest()[:12]

# Cache per entità specifiche
collaborators_cache = EntityCache('collaborators', ttl=1800)  # 30 minuti
projects_cache = EntityCache('projects', ttl=3600)           # 1 ora
attendances_cache = EntityCache('attendances', ttl=900)     # 15 minuti
assignments_cache = EntityCache('assignments', ttl=1800)    # 30 minuti

# Cache per query aggregate
@cache_result(ttl=1800, key_prefix="stats")
def cache_dashboard_stats(*args, **kwargs):
    """Cache per statistiche dashboard"""
    pass

@cache_result(ttl=3600, key_prefix="reports")
def cache_reports(*args, **kwargs):
    """Cache per report"""
    pass

# Utility per warming cache
def warm_cache():
    """Pre-carica cache con dati frequenti"""
    logger.info("Starting cache warm-up...")

    try:
        # Qui potresti pre-caricare dati frequenti
        # Esempio: lista collaboratori attivi, progetti in corso, etc.
        pass
    except Exception as e:
        logger.error(f"Error during cache warm-up: {e}")

    logger.info("Cache warm-up completed")

# Cleanup periodico
def cleanup_expired_cache():
    """Pulisci cache scaduta (solo per memory cache)"""
    if cache_manager.redis_client:
        return  # Redis gestisce automaticamente TTL

    now = time.time()
    expired_keys = []

    for key, entry in cache_manager._memory_cache.items():
        if entry.expires_at and now > entry.expires_at:
            expired_keys.append(key)

    for key in expired_keys:
        cache_manager.delete(key.replace('gestionale:', ''))

    if expired_keys:
        logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")

# Health check per cache
def get_cache_health() -> Dict[str, Any]:
    """Stato di salute del sistema cache"""
    stats = cache_manager.get_stats()

    health_status = 'healthy'
    issues = []

    # Controlla hit rate
    if stats['hit_rate'] < 0.5 and stats['total_requests'] > 100:
        health_status = 'degraded'
        issues.append('Low cache hit rate')

    # Controlla utilizzo memoria (solo memory cache)
    if 'memory_usage_bytes' in stats:
        if stats['memory_usage_bytes'] > 100 * 1024 * 1024:  # 100MB
            health_status = 'degraded'
            issues.append('High memory cache usage')

    return {
        'status': health_status,
        'backend': stats['backend'],
        'stats': stats,
        'issues': issues,
        'timestamp': datetime.utcnow().isoformat()
    }