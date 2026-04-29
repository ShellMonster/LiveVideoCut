import time

from app.services.memory_cache import FingerprintMemoryCache, TTLMemoryCache, path_fingerprint


def test_ttl_memory_cache_expires_and_evicts_lru():
    cache = TTLMemoryCache(max_size=2)
    cache.set("a", 1, ttl_seconds=10)
    cache.set("b", 2, ttl_seconds=0.01)

    assert cache.get("a") == 1
    time.sleep(0.02)
    assert cache.get("b") is None

    cache.set("c", 3, ttl_seconds=10)
    cache.set("d", 4, ttl_seconds=10)
    assert cache.get("a") is None
    assert cache.get("c") == 3
    assert cache.get("d") == 4


def test_fingerprint_memory_cache_invalidates_on_fingerprint_change_and_evicts_lru():
    cache = FingerprintMemoryCache(max_size=2)
    cache.set("a", ("v1",), 1)

    assert cache.get("a", ("v1",)) == 1
    assert cache.get("a", ("v2",)) is None

    cache.set("a", ("v1",), 1)
    cache.set("b", ("v1",), 2)
    assert cache.get("a", ("v1",)) == 1
    cache.set("c", ("v1",), 3)
    assert cache.get("b", ("v1",)) is None
    assert cache.get("a", ("v1",)) == 1
    assert cache.get("c", ("v1",)) == 3


def test_path_fingerprint_changes_when_file_changes(tmp_path):
    path = tmp_path / "payload.txt"
    before = path_fingerprint([path])

    path.write_text("hello")
    after = path_fingerprint([path])

    assert before != after
    assert after[0][1] == "file"
