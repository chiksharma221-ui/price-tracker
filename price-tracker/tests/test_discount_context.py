"""MRP, claimed discount, seller and badge extraction from saved pages."""
from pathlib import Path

from price_tracker.scraper import extract_discount_context, extract_price

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return (FIX / name).read_text(encoding="utf-8")


def test_amazon_layout_extracts_price_mrp_discount_seller_and_badge():
    url = "https://www.amazon.in/dp/B0TEST1234"
    html = load("amazon_deal.html")
    price = extract_price(url, html)
    ctx = extract_discount_context(url, html, price.price)
    assert price.price == 1499.0
    assert ctx["mrp"] == 3990.0
    assert ctx["claimed_discount_pct"] == 62.0
    assert ctx["seller"] == "Appario Retail Private Ltd"
    assert ctx["deal_badge"].lower() == "lightning deal"


def test_flipkart_layout_with_current_class_names():
    url = "https://www.flipkart.com/logitech/p/itmabc123"
    html = load("flipkart_deal.html")
    price = extract_price(url, html)
    ctx = extract_discount_context(url, html, price.price)
    assert price.price == 7495.0
    assert ctx["mrp"] == 10995.0
    assert ctx["claimed_discount_pct"] == 31.0
    assert ctx["seller"] == "RetailNet"


def test_json_ld_list_price_and_badge_text():
    url = "https://shop.example/mixer"
    html = load("json_ld_list_price.html")
    price = extract_price(url, html)
    ctx = extract_discount_context(url, html, price.price)
    assert price.price == 2999.0
    assert ctx["mrp"] == 5499.0
    assert ctx["claimed_discount_pct"] == round((5499 - 2999) / 5499 * 100, 1)
    assert ctx["deal_badge"].lower().startswith("lowest price")


def test_mrp_not_above_price_is_discarded():
    html = '<html><body><span class="price">₹500</span><del>₹450</del></body></html>'
    ctx = extract_discount_context("https://x.test/p", html, 500.0)
    assert ctx["mrp"] is None
    assert ctx["claimed_discount_pct"] is None
