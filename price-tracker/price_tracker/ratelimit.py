"""Per-site politeness: never hit the same domain more often than once every
PER_DOMAIN_MIN_INTERVAL_SECONDS, no matter how many workers are running.

With Redis, the lock is shared across processes and machines (SET NX PX, so
the slot expires on its own if a worker dies). Without Redis, an in-process
lock gives the same guarantee for the local thread pool.
"""
from __future__ import annotations

import logging
import threading
import time
from functools import lru_cache
from urllib.parse import urlparse

from .config import settings

logger = logging.getLogger(__name__)


def domain_of(url: str) -> str:
    host = urlparse(url).netloc.lower()
    parts = host.split(".")
    # amazon.in and www.amazon.in share one budget; keep 3 labels for e.g. co.uk
    return ".".join(parts[-3:] if len(parts) > 2 and len(parts[-1]) == 2 and len(parts[-2]) <= 3 else parts[-2:])


class LocalDomainRateLimiter:
    def __init__(self, interval: float):
        self.interval = interval
        self._next_allowed: dict[str, float] = {}
        self._lock = threading.Lock()

    def acquire(self, domain: str) -> float:
        """Block until this domain may be hit; returns seconds waited."""
        with self._lock:
            now = time.monotonic()
            slot = max(now, self._next_allowed.get(domain, 0.0))
            self._next_allowed[domain] = slot + self.interval
        wait = slot - now
        if wait > 0:
            time.sleep(wait)
        return wait


class RedisDomainRateLimiter:
    def __init__(self, client, interval: float, poll: float = 0.25):
        self.client = client
        self.interval_ms = int(interval * 1000)
        self.poll = poll

    def acquire(self, domain: str) -> float:
        start = time.monotonic()
        key = f"ratelimit:{domain}"
        while not self.client.set(key, "1", nx=True, px=self.interval_ms):
            time.sleep(self.poll)
        return time.monotonic() - start


@lru_cache(maxsize=1)
def get_limiter():
    interval = settings.per_domain_min_interval_seconds
    if settings.redis_configured:
        try:
            import redis
            client = redis.Redis.from_url(settings.redis_url)
            client.ping()
            return RedisDomainRateLimiter(client, interval)
        except Exception as exc:  # pragma: no cover - depends on external service
            logger.warning("Redis unavailable for rate limiting (%s); using local limiter.", exc)
    return LocalDomainRateLimiter(interval)
