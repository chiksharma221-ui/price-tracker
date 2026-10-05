"""Distributed checking with RQ (Redis Queue).

    scheduler  --enqueue-->  Redis "scrape" queue  -->  N x `rq worker scrape`

The scheduler only enqueues one small job per product; any number of worker
processes (or machines) pick them up. If Redis isn't configured, dispatch
falls back to the local thread pool in tracker.check_all, so the project
still runs with zero infrastructure.

Note: queue mode needs a shared database (MongoDB). The JSON store is for a
single process only.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from .config import settings
from .storage import Store, get_store
from .tracker import check_all, check_product

logger = logging.getLogger(__name__)
QUEUE_NAME = "scrape"


@lru_cache(maxsize=1)
def _worker_store() -> Store:
    return get_store()


def check_product_job(product_id: str) -> dict:
    """Entry point executed by `rq worker`. Must stay importable by path."""
    store = _worker_store()
    product = store.get_product(product_id)
    if product is None:
        return {"product_id": product_id, "status": "missing"}
    check_product(store, product)
    latest = product.latest_price
    return {"product_id": product_id, "status": "ok", "price": latest.price if latest else None}


def _queue():
    if not settings.redis_configured:
        return None
    try:
        import redis
        from rq import Queue
        conn = redis.Redis.from_url(settings.redis_url)
        conn.ping()
        return Queue(QUEUE_NAME, connection=conn)
    except Exception as exc:  # pragma: no cover - depends on external service
        logger.warning("Queue unavailable (%s); checking in-process instead.", exc)
        return None


def dispatch_all(store: Store) -> dict:
    queue = _queue()
    products = store.list_products()
    if queue is None:
        check_all(store)
        return {"mode": "local", "checked": len(products)}
    for product in products:
        queue.enqueue(check_product_job, product.id, job_timeout=120,
                      result_ttl=3600, job_id=None, description=f"check {product.name[:40]}")
    return {"mode": "queue", "enqueued": len(products)}
