import time
from collections import OrderedDict
from pathlib import Path
from threading import RLock
from typing import Any


class TTLMemoryCache:
    def __init__(self, max_size: int = 128):
        self.max_size = max_size
        self._items: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = RLock()

    def get(self, key: str) -> Any | None:
        now = time.monotonic()
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at <= now:
                self._items.pop(key, None)
                return None
            self._items.move_to_end(key)
            return value

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        with self._lock:
            self._items[key] = (time.monotonic() + ttl_seconds, value)
            self._items.move_to_end(key)
            while len(self._items) > self.max_size:
                self._items.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


class FingerprintMemoryCache:
    def __init__(self, max_size: int = 128):
        self.max_size = max_size
        self._items: OrderedDict[str, tuple[tuple[Any, ...], Any]] = OrderedDict()
        self._lock = RLock()

    def get(self, key: str, fingerprint: tuple[Any, ...]) -> Any | None:
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            cached_fingerprint, value = item
            if cached_fingerprint != fingerprint:
                self._items.pop(key, None)
                return None
            self._items.move_to_end(key)
            return value

    def set(self, key: str, fingerprint: tuple[Any, ...], value: Any) -> None:
        with self._lock:
            self._items[key] = (fingerprint, value)
            self._items.move_to_end(key)
            while len(self._items) > self.max_size:
                self._items.popitem(last=False)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._items.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


def path_fingerprint(paths: list[Path]) -> tuple[Any, ...]:
    parts: list[tuple[str, str, int, int, int]] = []
    for path in paths:
        try:
            if not path.exists():
                parts.append((path.as_posix(), "missing", 0, 0, 0))
                continue
            if path.is_file():
                stat = path.stat()
                parts.append((path.as_posix(), "file", stat.st_mtime_ns, stat.st_size, 1))
                continue
            latest_mtime = path.stat().st_mtime_ns
            total_size = 0
            file_count = 0
            for child in path.rglob("*"):
                if not child.is_file():
                    continue
                stat = child.stat()
                latest_mtime = max(latest_mtime, stat.st_mtime_ns)
                total_size += stat.st_size
                file_count += 1
            parts.append((path.as_posix(), "dir", latest_mtime, total_size, file_count))
        except OSError:
            parts.append((path.as_posix(), "error", 0, 0, 0))
    return tuple(parts)
