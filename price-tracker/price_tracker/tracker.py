"""Core orchestration: record observations, decide on alerts, run checks.

`record_observation` is the single place where a new price enters the
system, whether it came from the scraper or from the Chrome extension, so
alerting behaves identically for both.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from .config import settings
from .models import AlertEvent, PricePoint, Product
from .notifier import notify_price_drop
from .scraper import ScrapeError, scrape_price
from .storage import Store

logger = logging.getLogger(__name__)


def record_observation(store: Store, product: Product, point: PricePoint) -> bool:
    """Store a price point and alert if warranted. Returns True if an alert fired."""
    previous = product.latest_price
    # All-time low *before* this point, otherwise it would be its own low.
    all_time_low_before = product.all_time_low.price if product.history else None
    is_new_low = all_time_low_before is None or point.price < all_time_low_before

    store.append_price(product.id, point)
    product.history.append(point)

    should_alert = False
    if product.target_price is not None and point.price <= product.target_price:
        should_alert = True
    elif previous is not None and point.price < previous.price and is_new_low:
        should_alert = True
    if should_alert and product.last_alert_price == point.price:
        should_alert = False  # don't re-alert at the same price

    if should_alert:
        old_price = previous.price if previous else point.price
        notify_price_drop(
            product_name=product.name, url=product.url, old_price=old_price,
            new_price=point.price, currency=point.currency, is_all_time_low=is_new_low,
        )
        store.add_alert(AlertEvent(
            product_id=product.id, product_name=product.name, url=product.url,
            old_price=old_price, new_price=point.price, currency=point.currency,
            is_all_time_low=is_new_low,
        ))
        store.update_last_alert_price(product.id, point.price)
        product.last_alert_price = point.price
    return should_alert


def check_product(store: Store, product: Product) -> Product:
    """Scrape one product's current price and discount context, then record it."""
    try:
        result = scrape_price(product.url)
    except ScrapeError as exc:
        logger.error("Skipping %s (%s): %s", product.name, product.id, exc)
        return product

    point = PricePoint(
        price=result.price, currency=result.currency, in_stock=result.in_stock,
        mrp=result.mrp, claimed_discount_pct=result.claimed_discount_pct,
        seller=result.seller, deal_badge=result.deal_badge, source="scraper",
    )
    alerted = record_observation(store, product, point)
    logger.info(
        "%s: %s %.2f (mrp=%s, claimed=%s%%)%s", product.name, result.currency, result.price,
        result.mrp, result.claimed_discount_pct, " -- ALERT SENT" if alerted else "",
    )
    return product


def check_all(store: Store) -> list[Product]:
    """Check every product concurrently in a local thread pool. Requests to
    the same site are still serialised by the per-domain rate limiter."""
    products = store.list_products()
    if not products:
        return []
    with ThreadPoolExecutor(max_workers=max(1, settings.scrape_concurrency)) as pool:
        return list(pool.map(lambda p: check_product(store, p), products))
