from datetime import datetime, timedelta, timezone
from pathlib import Path

from price_tracker.analysis.features import compute_features
from price_tracker.analysis.predictor import BUY, WAIT, recommend
from price_tracker.models import PricePoint, SaleEvent

NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)
NO_MODEL = Path("/nonexistent/model.joblib")


def hist(prices, step_days=1):
    start = NOW - timedelta(days=step_days * (len(prices) - 1))
    return [PricePoint(price=p, currency="INR", checked_at=(start + timedelta(days=i * step_days)).isoformat())
            for i, p in enumerate(prices)]


def test_wait_when_sale_is_near():
    sale = SaleEvent(name="Sale", start=(NOW + timedelta(days=10)).isoformat(), end=(NOW + timedelta(days=15)).isoformat())
    rec = recommend(hist([1000] * 20), [sale], model_path=NO_MODEL)
    assert rec.action == WAIT and "10 days" in rec.reason


def test_buy_at_30_day_low_without_upcoming_sale():
    rec = recommend(hist([1200] * 15 + [1000]), [], model_path=NO_MODEL)
    assert rec.action == BUY


def test_wait_on_falling_trend():
    rec = recommend(hist([1000 - i * 15 for i in range(10)]), [], model_path=NO_MODEL)
    assert rec.action == WAIT  # at its low, but still falling steadily
    assert rec.source == "rules"


def test_features_have_no_lookahead():
    h = hist([1000] * 10 + [500] * 5)
    at = h[9].timestamp
    f = compute_features(h, [], at=at)
    assert f.pct_above_min_30d == 0  # the later 500s are invisible at time `at`


def test_buy_is_withheld_when_discount_is_not_real():
    from price_tracker.analysis.honesty import HonestyReport
    from price_tracker.analysis.predictor import NEUTRAL, Recommendation, reconcile

    report = HonestyReport(verdict="misleading", score=30, confidence="high", current_price=990,
                           currency="INR", baseline_price=1000, real_discount_pct=1.0,
                           claimed_discount_pct=60, mrp=2500, sale_name="Sale")
    rec = reconcile(Recommendation(BUY, "medium", "low", "rules"), report)
    assert rec.action == NEUTRAL and "no real discount" in rec.reason.lower()
