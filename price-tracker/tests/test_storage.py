from price_tracker.models import AlertEvent, PricePoint, Product
from price_tracker.storage import JsonStore


def test_json_store_round_trip(tmp_path):
    store = JsonStore(tmp_path / "store.json")
    product = Product(url="https://x.test/p", name="Widget", target_price=99.0)
    store.add_product(product)

    fetched = store.get_product(product.id)
    assert fetched is not None
    assert fetched.name == "Widget"
    assert fetched.target_price == 99.0

    store.append_price(product.id, PricePoint(price=79.0, currency="INR"))
    fetched = store.get_product(product.id)
    assert fetched.latest_price.price == 79.0

    store.update_last_alert_price(product.id, 79.0)
    fetched = store.get_product(product.id)
    assert fetched.last_alert_price == 79.0

    assert store.remove_product(product.id) is True
    assert store.get_product(product.id) is None


def test_json_store_lists_multiple_products(tmp_path):
    store = JsonStore(tmp_path / "store.json")
    store.add_product(Product(url="https://x.test/1", name="A"))
    store.add_product(Product(url="https://x.test/2", name="B"))
    names = sorted(p.name for p in store.list_products())
    assert names == ["A", "B"]


def test_json_store_alert_log_orders_newest_first(tmp_path):
    store = JsonStore(tmp_path / "store.json")
    store.add_alert(AlertEvent(
        product_id="p1", product_name="First", url="https://x.test/1",
        old_price=100, new_price=90, currency="INR", is_all_time_low=False,
        created_at="2026-01-01T00:00:00+00:00",
    ))
    store.add_alert(AlertEvent(
        product_id="p2", product_name="Second", url="https://x.test/2",
        old_price=200, new_price=150, currency="INR", is_all_time_low=True,
        created_at="2026-02-01T00:00:00+00:00",
    ))
    alerts = store.list_alerts()
    assert [a.product_name for a in alerts] == ["Second", "First"]


def test_json_store_alert_log_respects_limit(tmp_path):
    store = JsonStore(tmp_path / "store.json")
    for i in range(5):
        store.add_alert(AlertEvent(
            product_id="p1", product_name=f"Item {i}", url="https://x.test",
            old_price=100, new_price=90, currency="INR", is_all_time_low=False,
        ))
    assert len(store.list_alerts(limit=3)) == 3
