import json

from price_tracker.models import PricePoint, Product, SaleEvent
from price_tracker.storage import JsonStore
from price_tracker.urls import canonical_url


def test_migrates_embedded_history_from_old_format(tmp_path):
    path = tmp_path / "store.json"
    path.write_text(json.dumps({"products": [{
        "id": "p1", "url": "https://x.test/a", "name": "Old", "target_price": None,
        "created_at": "2026-01-01T00:00:00+00:00",
        "history": [{"price": 10.0, "currency": "INR", "checked_at": "2026-01-01T00:00:00+00:00", "in_stock": True}],
    }], "alerts": []}))
    store = JsonStore(path)
    product = store.get_product("p1")
    assert [p.price for p in product.history] == [10.0]
    raw = json.loads(path.read_text())
    assert "history" not in raw["products"][0]
    assert raw["observations"][0]["product_id"] == "p1"


def test_find_by_url_ignores_tracking_params(tmp_path):
    store = JsonStore(tmp_path / "s.json")
    store.add_product(Product(url="https://www.amazon.in/boAt-Rockerz/dp/B0ABCDEFGH/ref=sr_1_3?tag=x", name="A"))
    found = store.find_product_by_url("https://amazon.in/dp/B0ABCDEFGH?th=1")
    assert found and found.name == "A"


def test_history_is_sorted_and_removed_with_product(tmp_path):
    store = JsonStore(tmp_path / "s.json")
    p = Product(url="https://x.test/b", name="B")
    store.add_product(p)
    store.append_price(p.id, PricePoint(price=2, currency="INR", checked_at="2026-02-02T00:00:00+00:00"))
    store.append_price(p.id, PricePoint(price=1, currency="INR", checked_at="2026-02-01T00:00:00+00:00"))
    assert [x.price for x in store.get_history(p.id)] == [1, 2]
    store.remove_product(p.id)
    assert store.list_observations() == {}


def test_sale_events_roundtrip(tmp_path):
    store = JsonStore(tmp_path / "s.json")
    e = SaleEvent(name="Diwali", start="2026-10-20", end="2026-10-27")
    store.add_sale_event(e)
    assert store.list_sale_events()[0].name == "Diwali"
    assert store.remove_sale_event(e.id)


def test_canonical_urls():
    assert canonical_url("https://www.flipkart.com/logi-mouse/p/itmABC123?pid=ACCX&lid=1") == \
        "https://flipkart.com/p/itmabc123?pid=ACCX"
    assert canonical_url("https://shop.test/item/?utm=1") == "https://shop.test/item"
