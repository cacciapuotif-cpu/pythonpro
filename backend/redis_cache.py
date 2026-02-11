# =================================================================
# FILE: redis_cache.py
# =================================================================
# SCOPO: Implementazione caching con Redis per performance
#
# Redis è un database in-memory key-value estremamente veloce,
# ideale per caching dati frequentemente accessati.
#
# BENEFICI:
# - Riduce carico database (meno query)
# - Riduce latenza API (risposte più veloci)
# - Migliora scalabilità (cache condivisa tra istanze)
#
# STRATEGIA CACHING:
# - Cache aside: App controlla cache prima di DB
# - TTL (Time To Live): Cache expire automaticamente
# - Invalidazione selettiva: Rimuovi cache quando dati cambiano
# =================================================================

import redis
import json
import logging
from typing import Optional, Any, Callable
from functools import wraps
import os
import hashlib

# Setup logging
logger = logging.getLogger(__name__)

# =================================================================
# REDIS CONNECTION
# =================================================================

class RedisCache:
    """
    Wrapper per gestione cache Redis con pattern comuni.

    FEATURES:
    - Connection pooling
    - Serializzazione automatica JSON
    - TTL configurabile
    - Error handling graceful (fallback se Redis down)
    - Cache invalidation
    """

    def __init__(
        self,
        host: str = None,
        port: int = 6379,
        db: int = 0,
        password: str = None,
        decode_responses: bool = True,
        max_connections: int = 50
    ):
        """
        Inizializza connessione Redis.

        PARAMETRI:
            host: Redis host (default: env REDIS_HOST o localhost)
            port: Redis port (default: 6379)
            db: Database number (0-15)
            password: Password autenticazione (se configurato)
            decode_responses: Decode automatico bytes a string
            max_connections: Max connessioni nel pool
        """
        # Leggi configurazione da environment
        self.host = host or os.getenv('REDIS_HOST', 'localhost')
        self.port = port
        self.db = db
        self.password = password or os.getenv('REDIS_PASSWORD')

        # Pool connessioni per performance
        self.pool = redis.ConnectionPool(
            host=self.host,
            port=self.port,
            db=self.db,
            password=self.password,
            decode_responses=decode_responses,
            max_connections=max_connections,
            socket_timeout=5,
            socket_connect_timeout=5
        )

        # Client Redis
        self.redis_client = redis.Redis(connection_pool=self.pool)

        # Verifica connessione
        try:
            self.redis_client.ping()
            logger.info(f"✅ Redis connected: {self.host}:{self.port}")
        except redis.ConnectionError as e:
            logger.warning(f"⚠️ Redis connection failed: {e}")
            self.redis_client = None  # Fallback: no cache


    def _is_available(self) -> bool:
        """Verifica se Redis è disponibile"""
        return self.redis_client is not None


    def get(self, key: str) -> Optional[Any]:
        """
        Recupera valore da cache.

        PARAMETRI:
            key: Chiave cache

        RETURNS:
            Valore deserializzato o None se non trovato/errore

        ESEMPIO:
            cache = RedisCache()
            user_data = cache.get("user:123")
        """
        if not self._is_available():
            return None

        try:
            value = self.redis_client.get(key)
            if value is None:
                logger.debug(f"Cache MISS: {key}")
                return None

            logger.debug(f"Cache HIT: {key}")
            # Deserializza JSON
            return json.loads(value)

        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Redis GET error for key {key}: {e}")
            return None


    def set(
        self,
        key: str,
        value: Any,
        ttl: int = 300  # 5 minuti default
    ) -> bool:
        """
        Salva valore in cache con TTL.

        PARAMETRI:
            key: Chiave cache
            value: Valore (sarà serializzato in JSON)
            ttl: Time-to-live in secondi (default: 300 = 5min)

        RETURNS:
            True se successo, False se errore

        ESEMPIO:
            cache.set("user:123", {"name": "Mario"}, ttl=600)
        """
        if not self._is_available():
            return False

        try:
            # Serializza in JSON
            serialized = json.dumps(value, default=str)

            # Salva con expire automatico
            self.redis_client.setex(
                name=key,
                time=ttl,
                value=serialized
            )

            logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")
            return True

        except (redis.RedisError, TypeError, ValueError) as e:
            logger.error(f"Redis SET error for key {key}: {e}")
            return False


    def delete(self, key: str) -> bool:
        """
        Elimina chiave da cache (invalidation).

        PARAMETRI:
            key: Chiave da eliminare

        RETURNS:
            True se eliminata, False altrimenti

        USO:
            # Quando si aggiorna un collaboratore:
            cache.delete("collaborator:123")
            cache.delete("collaborators:all")
        """
        if not self._is_available():
            return False

        try:
            deleted = self.redis_client.delete(key)
            if deleted:
                logger.debug(f"Cache DELETED: {key}")
            return deleted > 0

        except redis.RedisError as e:
            logger.error(f"Redis DELETE error for key {key}: {e}")
            return False


    def delete_pattern(self, pattern: str) -> int:
        """
        Elimina tutte le chiavi che matchano pattern.

        PARAMETRI:
            pattern: Pattern con wildcards (* e ?)

        RETURNS:
            Numero chiavi eliminate

        ESEMPIO:
            # Elimina tutte le cache collaboratori:
            cache.delete_pattern("collaborator:*")

            # Elimina cache specifiche:
            cache.delete_pattern("user:*:profile")
        """
        if not self._is_available():
            return 0

        try:
            # Trova chiavi matchanti
            keys = self.redis_client.keys(pattern)
            if not keys:
                return 0

            # Elimina in batch
            deleted = self.redis_client.delete(*keys)
            logger.info(f"Cache DELETED pattern '{pattern}': {deleted} keys")
            return deleted

        except redis.RedisError as e:
            logger.error(f"Redis DELETE_PATTERN error for {pattern}: {e}")
            return 0


    def clear_all(self) -> bool:
        """
        Pulisce TUTTA la cache (ATTENZIONE: operazione distruttiva).

        USO RARO:
        - Dopo deploy con breaking changes
        - Reset ambiente sviluppo
        - Emergency troubleshooting

        RETURNS:
            True se successo
        """
        if not self._is_available():
            return False

        try:
            self.redis_client.flushdb()
            logger.warning("⚠️ ENTIRE CACHE CLEARED")
            return True

        except redis.RedisError as e:
            logger.error(f"Redis FLUSHDB error: {e}")
            return False


    def get_ttl(self, key: str) -> int:
        """
        Ottieni TTL rimanente per una chiave.

        RETURNS:
            Secondi rimanenti, -1 se chiave senza expire, -2 se non esiste
        """
        if not self._is_available():
            return -2

        try:
            return self.redis_client.ttl(key)
        except redis.RedisError:
            return -2


    def exists(self, key: str) -> bool:
        """
        Verifica se chiave esiste in cache.

        RETURNS:
            True se esiste, False altrimenti
        """
        if not self._is_available():
            return False

        try:
            return self.redis_client.exists(key) > 0
        except redis.RedisError:
            return False


# =================================================================
# SINGLETON INSTANCE
# =================================================================
# Istanza globale condivisa da tutta l'app
_cache_instance: Optional[RedisCache] = None

def get_cache() -> RedisCache:
    """
    Ottieni istanza singleton cache.

    Pattern Singleton: una sola connessione Redis per app.

    USO:
        from redis_cache import get_cache
        cache = get_cache()
        cache.set("mykey", "myvalue")
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RedisCache()
    return _cache_instance


# =================================================================
# DECORATOR PER CACHING AUTOMATICO
# =================================================================

def cached(
    ttl: int = 300,
    key_prefix: str = "",
    key_builder: Optional[Callable] = None
):
    """
    Decorator per caching automatico funzioni.

    PARAMETRI:
        ttl: Time-to-live cache in secondi
        key_prefix: Prefisso chiave cache (es. "collaborators:")
        key_builder: Funzione custom per generare chiave cache

    ESEMPIO BASE:
        @cached(ttl=600, key_prefix="collaborators:")
        def get_collaborators(db, skip=0, limit=100):
            return db.query(Collaborator).offset(skip).limit(limit).all()

    ESEMPIO CUSTOM KEY:
        @cached(
            ttl=300,
            key_builder=lambda db, collab_id: f"collaborator:{collab_id}"
        )
        def get_collaborator(db, collab_id: int):
            return db.query(Collaborator).filter_by(id=collab_id).first()

    COME FUNZIONA:
    1. Calcola chiave cache da args/kwargs
    2. Controlla se presente in cache
    3. Se HIT: ritorna valore cached
    4. Se MISS: esegue funzione, salva in cache, ritorna risultato
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()

            # Genera chiave cache
            if key_builder:
                # Key builder custom
                cache_key = key_builder(*args, **kwargs)
            else:
                # Key builder default: hash di args e kwargs
                # Formato: prefix:function_name:hash(args+kwargs)
                func_name = func.__name__
                args_str = str(args) + str(sorted(kwargs.items()))
                args_hash = hashlib.md5(args_str.encode()).hexdigest()[:8]
                cache_key = f"{key_prefix}{func_name}:{args_hash}"

            # Tenta recupero da cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache HIT for {func_name}")
                return cached_value

            # Cache MISS: esegui funzione
            logger.debug(f"Cache MISS for {func_name}")
            result = func(*args, **kwargs)

            # Salva in cache
            # NOTA: result deve essere serializzabile in JSON
            # Per oggetti SQLAlchemy, convertire prima in dict
            try:
                cache.set(cache_key, result, ttl=ttl)
            except TypeError as e:
                logger.warning(f"Cannot cache result of {func_name}: {e}")

            return result

        # Aggiungi metodo per invalidare cache
        def invalidate(*args, **kwargs):
            """Invalida cache per questa funzione con questi args"""
            cache = get_cache()
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                func_name = func.__name__
                args_str = str(args) + str(sorted(kwargs.items()))
                args_hash = hashlib.md5(args_str.encode()).hexdigest()[:8]
                cache_key = f"{key_prefix}{func_name}:{args_hash}"
            cache.delete(cache_key)

        wrapper.invalidate = invalidate
        return wrapper

    return decorator


# =================================================================
# PATTERN CACHE-ASIDE
# =================================================================

class CacheAside:
    """
    Helper per implementare pattern Cache-Aside manualmente.

    PATTERN:
    1. App controlla cache
    2. Se MISS: query DB, salva in cache
    3. Se HIT: ritorna da cache

    USO:
        cache_aside = CacheAside(cache_key="user:123", ttl=600)

        user = cache_aside.get_or_set(
            getter=lambda: db.query(User).filter_by(id=123).first()
        )
    """

    def __init__(self, cache_key: str, ttl: int = 300):
        self.cache_key = cache_key
        self.ttl = ttl
        self.cache = get_cache()

    def get_or_set(self, getter: Callable) -> Any:
        """
        Ottieni da cache o esegui getter e salva risultato.

        PARAMETRI:
            getter: Funzione senza argomenti che recupera dato

        RETURNS:
            Valore cached o risultato getter
        """
        # Try cache first
        cached_value = self.cache.get(self.cache_key)
        if cached_value is not None:
            return cached_value

        # Cache MISS: esegui getter
        result = getter()

        # Salva in cache
        if result is not None:
            self.cache.set(self.cache_key, result, ttl=self.ttl)

        return result


# =================================================================
# ESEMPI USO
# =================================================================
"""
# ESEMPIO 1: Uso base
from redis_cache import get_cache

cache = get_cache()

# Salva in cache
cache.set("user:123", {"name": "Mario", "age": 30}, ttl=600)

# Recupera da cache
user = cache.get("user:123")
print(user)  # {"name": "Mario", "age": 30}

# Elimina da cache
cache.delete("user:123")


# ESEMPIO 2: Decorator
from redis_cache import cached

@cached(ttl=300, key_prefix="collaborators:")
def get_all_collaborators(db):
    '''Questa funzione verrà cachata automaticamente'''
    return db.query(Collaborator).all()

# Prima chiamata: query DB + save cache
collaborators = get_all_collaborators(db)

# Seconda chiamata (entro 5min): ritorna da cache
collaborators = get_all_collaborators(db)

# Invalidazione cache
get_all_collaborators.invalidate(db)


# ESEMPIO 3: Cache-Aside manuale
from redis_cache import CacheAside

def get_collaborator(db, collab_id: int):
    cache_aside = CacheAside(
        cache_key=f"collaborator:{collab_id}",
        ttl=600
    )

    return cache_aside.get_or_set(
        getter=lambda: db.query(Collaborator).filter_by(id=collab_id).first()
    )


# ESEMPIO 4: Invalidazione dopo update
def update_collaborator(db, collab_id: int, data: dict):
    '''Update collaborator e invalida cache'''

    # Update DB
    collaborator = db.query(Collaborator).filter_by(id=collab_id).first()
    for key, value in data.items():
        setattr(collaborator, key, value)
    db.commit()

    # Invalida cache
    cache = get_cache()
    cache.delete(f"collaborator:{collab_id}")
    cache.delete_pattern("collaborators:*")  # Invalida liste

    return collaborator
"""
