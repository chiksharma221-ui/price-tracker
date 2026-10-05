"""Unit tests for price extraction. All run offline against local fixture
HTML, so they don't depend on any live site being reachable or unchanged."""
from pathlib import Path

import pytest

from price_tracker.scraper import ScrapeError, extract_price, extract_title

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_extract_price_from_json_ld():
    html = _load("json_ld_product.html")
    result = extract_price("https://example-shop.test/p/1", html)
    assert result.price == 2499.00
    assert result.currency == "INR"
    assert result.in_stock is True


def test_extract_price_from_meta_tags():
    html = _load("meta_tag_product.html")
    result = extract_price("https://example-shop.test/p/2", html)
    assert result.price == 3199.00
    assert result.currency == "INR"


def test_extract_price_from_generic_sweep():
    html = _load("generic_sweep_product.html")
    result = extract_price("https://unknown-shop.test/p/3", html)
    assert result.price == 1299.00


def test_extract_price_raises_when_nothing_found():
    html = _load("no_price_page.html")
    with pytest.raises(ScrapeError):
        extract_price("https://example-shop.test/p/404", html)


def test_extract_title_prefers_og_title():
    html = _load("json_ld_product.html")
    assert extract_title(html, fallback="fallback") == "Wireless Headphones - Demo Store"


def test_extract_title_falls_back_to_plain_title_tag():
    html = _load("meta_tag_product.html")
    # og:title is present here too, so this also exercises that path
    assert extract_title(html, fallback="fallback") == "Mechanical Keyboard 87-Key"
