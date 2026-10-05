"""Feature extraction over a price history, shared by the rule-based and the
ML buy-or-wait predictors so both reason about exactly the same signals."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from statistics import mean, median, pstdev
from typing import Optional

from ..models import PricePoint, SaleEvent

FEATURE_NAMES = [
    "pct_above_min_30d",
    "pct_vs_median_30d",
    "slope_7d_pct_per_day",
    "volatility_30d",
    "days_to_next_sale",
    "in_sale",
    "claimed_discount_pct",
    "days_tracked",
    "consecutive_drops",
]
NO_UPCOMING_SALE_DAYS = 60.0


@dataclass
class Features:
    pct_above_min_30d: float
    pct_vs_median_30d: float
    slope_7d_pct_per_day: float
    volatility_30d: float
    days_to_next_sale: float
    in_sale: float
    claimed_discount_pct: float
    days_tracked: float
    consecutive_drops: float

    def vector(self) -> list[float]:
        return [getattr(self, name) for name in FEATURE_NAMES]

    def to_dict(self) -> dict:
        return asdict(self)


def window(history: list[PricePoint], end: datetime, days: float) -> list[PricePoint]:
    start = end - timedelta(days=days)
    return [p for p in history if start <= p.timestamp <= end]


def _slope_pct_per_day(points: list[PricePoint]) -> float:
    """Least-squares slope of price over time, as % of the mean price per day."""
    if len(points) < 2:
        return 0.0
    t0 = points[0].timestamp
    xs = [(p.timestamp - t0).total_seconds() / 86400 for p in points]
    ys = [p.price for p in points]
    x_bar, y_bar = mean(xs), mean(ys)
    denom = sum((x - x_bar) ** 2 for x in xs)
    if denom == 0 or y_bar == 0:
        return 0.0
    slope = sum((x - x_bar) * (y - y_bar) for x, y in zip(xs, ys)) / denom
    return slope / y_bar * 100


def active_sale(sales: list[SaleEvent], at: datetime) -> Optional[SaleEvent]:
    return next((s for s in sales if s.contains(at)), None)


def next_sale(sales: list[SaleEvent], at: datetime) -> Optional[SaleEvent]:
    upcoming = [s for s in sales if s.start_dt > at]
    return min(upcoming, key=lambda s: s.start_dt) if upcoming else None


def compute_features(history: list[PricePoint], sales: list[SaleEvent],
                     at: Optional[datetime] = None) -> Optional[Features]:
    """Features describing the price at time `at` (default: the latest point),
    using only information available at that moment -- no look-ahead, which
    matters when the same function builds training data from the past."""
    if not history:
        return None
    if at is None:
        at = history[-1].timestamp
    past = [p for p in history if p.timestamp <= at]
    if not past:
        return None
    current = past[-1]
    last30 = window(past, at, 30) or [current]
    prices30 = [p.price for p in last30]
    low30, med30 = min(prices30), median(prices30)
    upcoming = next_sale(sales, at)

    return Features(
        pct_above_min_30d=(current.price - low30) / low30 * 100 if low30 else 0.0,
        pct_vs_median_30d=(current.price - med30) / med30 * 100 if med30 else 0.0,
        slope_7d_pct_per_day=_slope_pct_per_day(window(past, at, 7)),
        volatility_30d=(pstdev(prices30) / mean(prices30)) if len(prices30) > 1 and mean(prices30) else 0.0,
        days_to_next_sale=min(NO_UPCOMING_SALE_DAYS, (upcoming.start_dt - at).total_seconds() / 86400)
        if upcoming else NO_UPCOMING_SALE_DAYS,
        in_sale=1.0 if active_sale(sales, at) else 0.0,
        claimed_discount_pct=current.claimed_discount_pct or 0.0,
        days_tracked=(at - past[0].timestamp).total_seconds() / 86400,
        consecutive_drops=float(_consecutive_drops(past)),
    )


def _consecutive_drops(points: list[PricePoint], cap: int = 10) -> int:
    """How many checks in a row the price has fallen, ending at the latest one.
    Separates a steady decline from a single one-off drop."""
    count = 0
    for prev, cur in zip(reversed(points[:-1]), reversed(points)):
        if cur.price < prev.price:
            count += 1
            if count >= cap:
                break
        else:
            break
    return count
