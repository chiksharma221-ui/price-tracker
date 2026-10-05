"""Unit tests for the alert-decision logic in tracker.check_product.

These tests fake out the scraper and notifier so they run instantly and
offline, and so we can precisely control the sequence of prices a "product"
reports across successive checks.
"""
from unittest.mock import patch

from price_tracker.models import Product
from price_tracker.scraper import ScrapedPrice
from price_tracker.storage import JsonStore
from price_tracker.tracker import check_product


def make_store(tmp_path):
    return JsonStore(tmp_path / "store.json")


@patch("price_tracker.tracker.notify_price_drop")
@patch("price_tracker.tracker.scrape_price")
def test_first_check_records_price_without_alert(mock_scrape, mock_notify, tmp_path):
    mock_scrape.return_value = ScrapedPrice(price=1000.0, currency="INR")
    store = make_store(tmp_path)
    product = Product(url="https://x.test/p", name="Widget")
    store.add_product(product)

    check_product(store, product)

    mock_notify.assert_not_called()
    assert product.latest_price.price == 1000.0


@patch("price_tracker.tracker.notify_price_drop")
@patch("price_tracker.tracker.scrape_price")
def test_price_drop_below_target_triggers_alert(mock_scrape, mock_notify, tmp_path):
    store = make_store(tmp_path)
    product = Product(url="https://x.test/p", name="Widget", target_price=900.0)
    store.add_product(product)

    mock_scrape.return_value = ScrapedPrice(price=1000.0, currency="INR")
    check_product(store, product)
    mock_notify.assert_not_called()

    mock_scrape.return_value = ScrapedPrice(price=850.0, currency="INR")
    check_product(store, product)
    mock_notify.assert_called_once()
    assert mock_notify.call_args.kwargs["new_price"] == 850.0


@patch("price_tracker.tracker.notify_price_drop")
@patch("price_tracker.tracker.scrape_price")
def test_new_all_time_low_triggers_alert_even_without_target(mock_scrape, mock_notify, tmp_path):
    store = make_store(tmp_path)
    product = Product(url="https://x.test/p", name="Widget")  # no target price set
    store.add_product(product)

    mock_scrape.return_value = ScrapedPrice(price=500.0, currency="INR")
    check_product(store, product)

    mock_scrape.return_value = ScrapedPrice(price=450.0, currency="INR")  # new low
    check_product(store, product)

    mock_notify.assert_called_once()
    assert mock_notify.call_args.kwargs["is_all_time_low"] is True


@patch("price_tracker.tracker.notify_price_drop")
@patch("price_tracker.tracker.scrape_price")
def test_price_increase_does_not_alert(mock_scrape, mock_notify, tmp_path):
    store = make_store(tmp_path)
    product = Product(url="https://x.test/p", name="Widget")
    store.add_product(product)

    mock_scrape.return_value = ScrapedPrice(price=500.0, currency="INR")
    check_product(store, product)

    mock_scrape.return_value = ScrapedPrice(price=600.0, currency="INR")
    check_product(store, product)

    mock_notify.assert_not_called()


@patch("price_tracker.tracker.notify_price_drop")
@patch("price_tracker.tracker.scrape_price")
def test_alert_is_recorded_in_store_alert_log(mock_scrape, mock_notify, tmp_path):
    store = make_store(tmp_path)
    product = Product(url="https://x.test/p", name="Widget", target_price=900.0)
    store.add_product(product)

    mock_scrape.return_value = ScrapedPrice(price=1000.0, currency="INR")
    check_product(store, product)

    mock_scrape.return_value = ScrapedPrice(price=850.0, currency="INR")
    check_product(store, product)

    alerts = store.list_alerts()
    assert len(alerts) == 1
    assert alerts[0].product_name == "Widget"
    assert alerts[0].new_price == 850.0


@patch("price_tracker.tracker.notify_price_drop")
@patch("price_tracker.tracker.scrape_price")
def test_does_not_re_alert_at_same_price(mock_scrape, mock_notify, tmp_path):
    store = make_store(tmp_path)
    product = Product(url="https://x.test/p", name="Widget", target_price=900.0)
    store.add_product(product)

    mock_scrape.return_value = ScrapedPrice(price=1000.0, currency="INR")
    check_product(store, product)

    mock_scrape.return_value = ScrapedPrice(price=800.0, currency="INR")
    check_product(store, product)
    assert mock_notify.call_count == 1

    # Simulate the scheduler running again before the price has changed at all.
    check_product(store, product)
    assert mock_notify.call_count == 1
