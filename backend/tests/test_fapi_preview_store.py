"""Garanzie single-use delle preview FAPI."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

import fapi_preview_store as preview_store


def test_pop_locale_e_atomico_con_conferme_concorrenti(monkeypatch):
    monkeypatch.setattr(preview_store, "_redis", None)
    with preview_store._local_lock:
        preview_store._local.clear()
    preview_store.store("token-concorrente", {"project_id": 11})

    with ThreadPoolExecutor(max_workers=12) as executor:
        risultati = list(
            executor.map(
                lambda _index: preview_store.pop("token-concorrente"),
                range(24),
            )
        )

    assert risultati.count({"project_id": 11}) == 1
    assert risultati.count(None) == 23


def test_pop_redis_usa_getdel_atomico(monkeypatch):
    class RedisFinto:
        def __init__(self):
            self.chiamate = []

        def getdel(self, key):
            self.chiamate.append(("getdel", key))
            return '{"project_id": 11}'

    redis_finto = RedisFinto()
    monkeypatch.setattr(preview_store, "_redis", redis_finto)

    assert preview_store.pop("token-redis") == {"project_id": 11}
    assert redis_finto.chiamate == [("getdel", "fapi_preview:token-redis")]
