"""Run a full check on a fixed interval.

With REDIS_URL set this process only *enqueues* work; start one or more
`rq worker scrape` processes to do the scraping. Without Redis it checks
everything itself, concurrently, in a thread pool.

    python -m price_tracker.scheduler
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from .config import settings
from .jobs import dispatch_all
from .storage import get_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def run_once() -> None:
    result = dispatch_all(get_store())
    logger.info("Dispatch complete: %s", result)


def main() -> None:
    logger.info("Starting scheduler (interval=%d min).", settings.scrape_interval_minutes)
    run_once()
    scheduler = BlockingScheduler()
    scheduler.add_job(run_once, "interval", minutes=settings.scrape_interval_minutes, max_instances=1)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down scheduler.")


if __name__ == "__main__":
    main()
