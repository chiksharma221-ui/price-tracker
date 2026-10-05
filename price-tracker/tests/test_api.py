"""API tests against a temporary JSON store (no network)."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import price_tracker.api as api_module
from price_tracker.models import PricePoint
from price_tracker.storage import JsonStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    store = JsonStore(tmp_path / "store.json")
    monkeypatch.setattr(api_module, "_store", store)
    monkeypatch.setattr(api_module, "_sales_cache", (0.0, []))
    monkeypatch.setattr(api_module.settings, "api_token", None)
    return TestClient(api_module.app), store


OBS = {"url": "https://www.amazon.in/some-slug/dp/B0ABCDEFGH?ref=x", "name": "Headphones",
       "price": 1499, "mrp": 3990, "claimed_discount_pct": 62, "deal_badge": "Lightning Deal"}


def test_observation_creates_product_and_returns_analysis(client):
    c, store = client
    r = c.post("/api/observations", json=OBS)
    assert r.status_code == 200
    body = r.json()
    assert body["tracked"] and body["observations"] == 1
    assert body["honesty"]["verdict"] == "insufficient_data"
    assert store.list_products()[0].history[0].source == "extension"


def test_repeated_identical_observation_is_deduplicated(client):
    c, _ = client
    c.post("/api/observations", json=OBS)
    r = c.post("/api/observations", json={**OBS, "url": "https://amazon.in/dp/B0ABCDEFGH"})
    assert r.json()["observations"] == 1


def test_lookup_reports_untracked_url(client):
    c, _ = client
    assert c.get("/api/lookup", params={"url": "https://x.test/unknown"}).json()["tracked"] is False


def test_token_required_when_configured(client, monkeypatch):
    c, _ = client
    monkeypatch.setattr(api_module.settings, "api_token", "secret")
    assert c.post("/api/observations", json=OBS).status_code == 401
    assert c.post("/api/observations", json=OBS, headers={"X-API-Token": "secret"}).status_code == 200


def test_sales_and_insights_with_history(client):
    c, store = client
    start = datetime.now(timezone.utc) - timedelta(days=2)
    sale = c.post("/api/sales", json={"name": "Test Sale", "start": start.isoformat(),
                                      "end": (start + timedelta(days=5)).isoformat()}).json()
    c.post("/api/observations", json={**OBS, "category": "Electronics"})
    product = store.list_products()[0]
    for d in range(45, 3, -1):  # usual price ~1500 before the sale
        t = datetime.now(timezone.utc) - timedelta(days=d)
        store.append_price(product.id, PricePoint(price=1550, currency="INR", checked_at=t.isoformat(), mrp=3990))
    store.append_price(product.id, PricePoint(price=1499, currency="INR", mrp=3990, claimed_discount_pct=62))

    prod = c.get(f"/api/products/{product.id}").json()
    assert prod["honesty"]["verdict"] == "misleading"
    assert "inflated_mrp" in {f["code"] for f in prod["honesty"]["flags"]}

    stats = c.get("/api/insights", params={"sale_id": sale["id"]}).json()
    assert stats["products_judged"] == 1
    assert stats["verdicts"]["Misleading"]["count"] == 1


def test_sale_validation(client):
    c, _ = client
    r = c.post("/api/sales", json={"name": "Bad", "start": "2026-10-10", "end": "2026-10-01"})
    assert r.status_code == 422
