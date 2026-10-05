"""Discount Truth engine: each flag, the verdicts, and the data guardrails."""
from datetime import datetime, timedelta, timezone

from price_tracker.analysis.honesty import (FLAG_CHEAPER_BEFORE, FLAG_FAKE_LOWEST,
                                            FLAG_INFLATED_MRP, FLAG_MRP_RAISED,
                                            FLAG_PRE_SALE_HIKE, VERDICT_GENUINE,
                                            VERDICT_INSUFFICIENT, VERDICT_MISLEADING,
                                            Flag, analyze, score_from_flags)
from price_tracker.models import PricePoint, SaleEvent

SALE_START = datetime(2026, 10, 20, tzinfo=timezone.utc)
SALE = SaleEvent(name="Diwali Sale", start=SALE_START.isoformat(),
                 end=(SALE_START + timedelta(days=6)).isoformat())


def series(price_fn, mrp_fn=lambda t, p: None, days_before=50, badge_fn=lambda t: None, until_day=2):
    points = []
    for d in range(-days_before, until_day + 1):
        t = SALE_START + timedelta(days=d, hours=12)
        price = price_fn(d)
        mrp = mrp_fn(d, price)
        points.append(PricePoint(
            price=price, currency="INR", checked_at=t.isoformat(), mrp=mrp,
            claimed_discount_pct=round((mrp - price) / mrp * 100, 1) if mrp else None,
            deal_badge=badge_fn(d)))
    return points


def flags_of(report):
    return {f.code for f in report.flags}


def test_genuine_discount():
    h = series(lambda d: 800 if d >= 0 else 1000, lambda d, p: 1050)
    r = analyze(h, [SALE])
    assert r.verdict == VERDICT_GENUINE
    assert r.baseline_price == 1000
    assert r.real_discount_pct == 20.0
    assert not flags_of(r) - {FLAG_CHEAPER_BEFORE}


def test_inflated_mrp_is_flagged_and_misleading():
    h = series(lambda d: 980 if d >= 0 else 1000, lambda d, p: 2500)
    r = analyze(h, [SALE])
    assert FLAG_INFLATED_MRP in flags_of(r)
    assert r.verdict == VERDICT_MISLEADING
    assert r.claimed_discount_pct > 55 and r.real_discount_pct < 5


def test_pre_sale_hike_is_excluded_from_baseline_and_flagged():
    def price(d):
        if -12 <= d < 0:
            return 1250   # hiked just before the sale
        return 1000 if d < 0 else 990
    h = series(price, lambda d, p: 1300)
    r = analyze(h, [SALE])
    assert FLAG_PRE_SALE_HIKE in flags_of(r)
    assert r.baseline_price == 1000  # the hike did not leak into the reference price
    assert r.real_discount_pct == 1.0


def test_fake_lowest_badge():
    h = series(lambda d: 700 if d == -30 else (950 if d >= 0 else 1000), lambda d, p: 1100,
               badge_fn=lambda d: "Lowest price in 30 days" if d >= 0 else None)
    r = analyze(h, [SALE])
    assert FLAG_FAKE_LOWEST in flags_of(r)
    assert r.verdict != VERDICT_GENUINE


def test_mrp_raised_during_tracking():
    h = series(lambda d: 800 if d >= 0 else 1000, lambda d, p: 1100 if d < -20 else 1800)
    r = analyze(h, [SALE])
    assert FLAG_MRP_RAISED in flags_of(r)


def test_insufficient_history_gives_no_score():
    h = series(lambda d: 900, lambda d, p: 1500, days_before=3)
    r = analyze(h, [SALE])
    assert r.verdict == VERDICT_INSUFFICIENT
    assert r.score is None


def test_outside_a_sale_uses_now_as_anchor():
    h = series(lambda d: 1000, lambda d, p: 1100, days_before=60, until_day=-20)
    r = analyze(h, [SALE])
    assert r.sale_name is None
    assert r.verdict == VERDICT_GENUINE


def test_any_real_problem_caps_score_below_genuine():
    assert score_from_flags([Flag(FLAG_MRP_RAISED, "medium", "", 12)]) <= 74
    assert score_from_flags([Flag(FLAG_CHEAPER_BEFORE, "low", "", 6)]) == 95


def test_analysis_at_a_past_moment_ignores_later_points():
    h = series(lambda d: 800 if d >= 0 else 1000, lambda d, p: 1050)
    before_sale = SALE_START - timedelta(days=1)
    r = analyze(h, [SALE], at=before_sale)
    assert r.current_price == 1000
