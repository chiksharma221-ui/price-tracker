"""Price scraping.

Design notes
------------
Real e-commerce sites change their markup often and some (Amazon, Flipkart)
actively try to block bots, so a scraper that hard-codes one site's CSS
selectors breaks constantly. This module instead layers three strategies,
tried in order, so it keeps working across a much wider range of sites:

1. Structured data first: most e-commerce sites embed machine-readable price
   info either as JSON-LD (schema.org/Product/Offer) or Open Graph / Twitter
   meta tags, *because search engines and social previews rely on it*. This
   is the most robust signal and rarely changes even when the visual design
   does.
2. Site-specific CSS selectors as a fallback, for the handful of big sites
   where structured data is absent or incomplete (a couple of examples are
   included for Amazon/Flipkart; add more under SITE_PARSERS as needed).
3. A last-resort generic price-regex sweep over visible text, so an unknown
   site still has a chance of working instead of failing outright.

Discount context
----------------
A selling price alone can't tell you whether a "60% off" claim is honest, so
after the price is found the page is mined separately for the *claimed*
context: the MRP / strike-through price, the advertised discount percentage,
the seller and any deal badge ("Lightning Deal", "Lowest price in 30 days").
These are extracted independently of which strategy found the price, because
structured data usually carries the selling price but not the MRP.

Every network call uses a realistic browser User-Agent, a randomized delay,
and retry-with-backoff so the scraper behaves politely rather than hammering
a target site (see config.py for the tunable knobs).
"""
from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .config import settings
from .ratelimit import domain_of, get_limiter

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

PRICE_RE = re.compile(r"[\d]{1,3}(?:[,\d]{0,10})?(?:\.\d{1,2})?")
CURRENCY_SYMBOLS = {"₹": "INR", "$": "USD", "€": "EUR", "£": "GBP"}


class ScrapeError(Exception):
    """Raised when a price could not be extracted from a page."""


@dataclass
class ScrapedPrice:
    price: float
    currency: str
    in_stock: bool = True
    mrp: Optional[float] = None
    claimed_discount_pct: Optional[float] = None
    seller: Optional[str] = None
    deal_badge: Optional[str] = None


def _clean_number(raw: str) -> Optional[float]:
    raw = raw.replace(",", "").strip()
    match = PRICE_RE.search(raw)
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def _detect_currency(raw: str, default: str = "INR") -> str:
    for symbol, code in CURRENCY_SYMBOLS.items():
        if symbol in raw:
            return code
    for code in ("INR", "USD", "EUR", "GBP"):
        if code in raw.upper():
            return code
    return default


def fetch_html(url: str) -> str:
    """Fetch a page's HTML with a polite delay, a browser UA and retries."""
    last_exc: Optional[Exception] = None
    domain = domain_of(url)
    for attempt in range(1, settings.max_retries + 1):
        get_limiter().acquire(domain)  # shared per-site budget across all workers
        delay = random.uniform(settings.min_delay_seconds, settings.max_delay_seconds)
        time.sleep(delay)
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        try:
            resp = requests.get(url, headers=headers, timeout=settings.request_timeout_seconds)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:  # pragma: no cover - network dependent
            last_exc = exc
            logger.warning("Attempt %d/%d failed for %s: %s", attempt, settings.max_retries, url, exc)
    raise ScrapeError(f"Could not fetch {url}: {last_exc}")


# --- Strategy 1: structured data (JSON-LD / Open Graph) --------------------

def _from_json_ld(soup: BeautifulSoup) -> Optional[ScrapedPrice]:
    import json

    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "{}")
        except (ValueError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            offers = item.get("offers") if isinstance(item, dict) else None
            if isinstance(offers, list):
                offers = offers[0] if offers else None
            if isinstance(offers, dict) and offers.get("price"):
                price = _clean_number(str(offers["price"]))
                if price is not None:
                    currency = offers.get("priceCurrency", "INR")
                    availability = str(offers.get("availability", "")).lower()
                    in_stock = "outofstock" not in availability
                    return ScrapedPrice(price, currency, in_stock)
    return None


def _from_meta_tags(soup: BeautifulSoup) -> Optional[ScrapedPrice]:
    meta_price_names = [
        ("meta", {"property": "product:price:amount"}),
        ("meta", {"property": "og:price:amount"}),
        ("meta", {"itemprop": "price"}),
        ("meta", {"name": "twitter:data1"}),
    ]
    for tag_name, attrs in meta_price_names:
        tag = soup.find(tag_name, attrs=attrs)
        if tag and tag.get("content"):
            price = _clean_number(tag["content"])
            if price is not None:
                currency_tag = soup.find("meta", attrs={"property": "product:price:currency"})
                currency = currency_tag["content"] if currency_tag and currency_tag.get("content") else "INR"
                return ScrapedPrice(price, currency)
    return None


# --- Strategy 2: site-specific CSS selectors --------------------------------

def _parse_amazon(soup: BeautifulSoup) -> Optional[ScrapedPrice]:
    selectors = [
        "span.a-price span.a-offscreen",
        "#priceblock_ourprice",
        "#priceblock_dealprice",
    ]
    for sel in selectors:
        tag = soup.select_one(sel)
        if tag and tag.text.strip():
            price = _clean_number(tag.text)
            if price is not None:
                return ScrapedPrice(price, _detect_currency(tag.text))
    return None


def _parse_flipkart(soup: BeautifulSoup) -> Optional[ScrapedPrice]:
    # Flipkart rotates its obfuscated class names; both current and older
    # generations are listed.
    tag = soup.select_one("div.Nx9bqj, div._30jeq3, div._16Jk6d, div._25b18c ._30jeq3")
    if tag and tag.text.strip():
        price = _clean_number(tag.text)
        if price is not None:
            return ScrapedPrice(price, _detect_currency(tag.text))
    return None


SITE_PARSERS: dict[str, Callable[[BeautifulSoup], Optional[ScrapedPrice]]] = {
    "amazon.": _parse_amazon,
    "flipkart.": _parse_flipkart,
}


def _site_specific(url: str, soup: BeautifulSoup) -> Optional[ScrapedPrice]:
    host = urlparse(url).netloc.lower()
    for key, parser in SITE_PARSERS.items():
        if key in host:
            return parser(soup)
    return None


# --- Strategy 3: last-resort generic sweep ----------------------------------

_GENERIC_PRICE_TAG_HINTS = ["price", "product-price", "offer-price", "sale-price"]


def _from_generic_sweep(soup: BeautifulSoup) -> Optional[ScrapedPrice]:
    for hint in _GENERIC_PRICE_TAG_HINTS:
        for tag in soup.find_all(attrs={"class": re.compile(hint, re.I)}):
            text = tag.get_text(strip=True)
            if any(sym in text for sym in CURRENCY_SYMBOLS) or re.search(r"\d", text):
                price = _clean_number(text)
                if price is not None:
                    return ScrapedPrice(price, _detect_currency(text))
    return None


def extract_price(url: str, html: str) -> ScrapedPrice:
    soup = BeautifulSoup(html, "html.parser")

    result = _from_json_ld(soup)
    if result:
        return result

    result = _from_meta_tags(soup)
    if result:
        return result

    result = _site_specific(url, soup)
    if result:
        return result

    result = _from_generic_sweep(soup)
    if result:
        return result

    raise ScrapeError(f"No price could be extracted from {url}")


# --- Discount context: MRP, claimed discount, seller, badges ---------------

_MRP_SELECTORS = {
    "amazon.": [
        "#corePriceDisplay_desktop_feature_div span.a-price.a-text-price span.a-offscreen",
        "span.basisPrice span.a-offscreen",
        "span.a-price.a-text-price span.a-offscreen",
        "#listPrice",
        "#priceblock_listprice",
    ],
    "flipkart.": ["div.yRaY8j", "div._3I9_wc"],
}
_DISCOUNT_SELECTORS = {
    "amazon.": ["span.savingsPercentage"],
    "flipkart.": ["div.UkUFwK span", "div._3Ay6Sb span"],
}
_SELLER_SELECTORS = {
    "amazon.": ["#sellerProfileTriggerId", "#merchantInfoFeature_feature_div .offer-display-feature-text-message"],
    "flipkart.": ["#sellerName span span", "#sellerName span"],
}
_GENERIC_MRP_HINT = re.compile(r"mrp|strike|was-?price|list-?price|original-?price|old-?price", re.I)
_BADGE_PATTERNS = re.compile(
    r"(lightning deal|deal of the day|limited time deal|lowest price[^.<]{0,30}|"
    r"bank offer|big billion|great indian festival|festive offer)",
    re.I,
)
_PERCENT_RE = re.compile(r"(\d{1,2}(?:\.\d)?)\s*%")


def _host_key(url: str, table: dict) -> Optional[str]:
    host = urlparse(url).netloc.lower()
    return next((k for k in table if k in host), None)


def _mrp_from_json_ld(soup: BeautifulSoup) -> Optional[float]:
    """schema.org lets an Offer carry a list/strike-through price via
    priceSpecification (priceType ListPrice/StrikethroughPrice) or highPrice."""
    import json

    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "{}")
        except (ValueError, TypeError):
            continue
        for item in data if isinstance(data, list) else [data]:
            if not isinstance(item, dict):
                continue
            offers = item.get("offers")
            for offer in offers if isinstance(offers, list) else [offers]:
                if not isinstance(offer, dict):
                    continue
                specs = offer.get("priceSpecification")
                for spec in specs if isinstance(specs, list) else [specs]:
                    if isinstance(spec, dict) and any(
                        k in str(spec.get("priceType", "")) for k in ("ListPrice", "StrikethroughPrice", "MSRP")
                    ):
                        value = _clean_number(str(spec.get("price", "")))
                        if value:
                            return value
                if offer.get("highPrice"):
                    value = _clean_number(str(offer["highPrice"]))
                    if value:
                        return value
    return None


def _first_text(soup: BeautifulSoup, selectors: list[str]) -> Optional[str]:
    for sel in selectors:
        tag = soup.select_one(sel)
        if tag and tag.get_text(strip=True):
            return tag.get_text(" ", strip=True)
    return None


def extract_discount_context(url: str, html: str, price: float) -> dict:
    """Return mrp, claimed_discount_pct, seller and deal_badge for a page.

    Any value that can't be found is None. An MRP that is not above the
    selling price is discarded as a mis-parse rather than recorded as a
    "discount" of zero or less.
    """
    soup = BeautifulSoup(html, "html.parser")
    mrp: Optional[float] = _mrp_from_json_ld(soup)

    key = _host_key(url, _MRP_SELECTORS)
    if mrp is None and key:
        text = _first_text(soup, _MRP_SELECTORS[key])
        mrp = _clean_number(text) if text else None

    if mrp is None:
        for tag in soup.find_all(["del", "s", "strike"]) + soup.find_all(attrs={"class": _GENERIC_MRP_HINT}):
            value = _clean_number(tag.get_text(strip=True))
            if value and value > price:
                mrp = value
                break

    if mrp is not None and mrp <= price:
        mrp = None

    claimed: Optional[float] = None
    dkey = _host_key(url, _DISCOUNT_SELECTORS)
    if dkey:
        text = _first_text(soup, _DISCOUNT_SELECTORS[dkey])
        match = _PERCENT_RE.search(text or "")
        if match:
            claimed = float(match.group(1))
    if claimed is None and mrp:
        claimed = round((mrp - price) / mrp * 100, 1)

    seller = None
    skey = _host_key(url, _SELLER_SELECTORS)
    if skey:
        seller = _first_text(soup, _SELLER_SELECTORS[skey])

    badge_match = _BADGE_PATTERNS.search(soup.get_text(" ", strip=True))
    deal_badge = badge_match.group(1).strip() if badge_match else None

    return {"mrp": mrp, "claimed_discount_pct": claimed, "seller": seller, "deal_badge": deal_badge}


def scrape_price(url: str) -> ScrapedPrice:
    """Fetch a product page and extract its price plus discount context.
    Raises ScrapeError."""
    html = fetch_html(url)
    result = extract_price(url, html)
    context = extract_discount_context(url, html, result.price)
    result.mrp = context["mrp"]
    result.claimed_discount_pct = context["claimed_discount_pct"]
    result.seller = context["seller"]
    result.deal_badge = context["deal_badge"]
    return result


def extract_title(html: str, fallback: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        return og_title["content"].strip()
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return fallback
