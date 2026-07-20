"""
Conftest globale della suite backend.

NEW-028: il RateLimitingMiddleware (request_middleware.py) tiene lo stato
in-memory per IP ("testclient") condiviso da TUTTA la suite, perche' l'app
FastAPI e' un singleton di modulo. Con la crescita della suite il budget
(120 req/min sul bucket "*") viene sforato dai test vicini nel tempo e test
non correlati falliscono con 429 in modo nondeterministico.

Il fixture autouse azzera lo stato del limiter prima di ogni test: ogni test
riparte con il budget pieno. I test che volessero verificare il rate limiting
entro il singolo test non sono influenzati (nessun test asserisce oggi un 429
cross-test).
"""
import pytest

from main import app
from request_middleware import RateLimitingMiddleware


def _iter_middleware_stack(asgi_app):
    seen = set()
    node = asgi_app
    while node is not None and id(node) not in seen:
        seen.add(id(node))
        yield node
        node = getattr(node, "app", None)


@pytest.fixture(autouse=True)
def _reset_rate_limiter_state():
    stack = getattr(app, "middleware_stack", None)
    for node in _iter_middleware_stack(stack):
        if isinstance(node, RateLimitingMiddleware):
            node.client_requests.clear()
    yield
