"""Discount Truth engine.

Answers one question for a listing: *is the advertised discount real?*

The seller's MRP is not a trustworthy reference -- it is the number that gets
inflated. Instead the engine builds its own reference price from what the
product actually sold for before the sale:

    anchor        = start of the active sale (or "now" outside a sale)
    hike window   = the HIKE_WINDOW_DAYS just before the anchor
    baseline      = median price in the BASELINE_DAYS before the hike window

Keeping the hike window out of the baseline is the important part: a seller
who raises the price two weeks before a sale and then "discounts" it back
would otherwise poison the very reference used to judge them.

From that it derives the real discount, compares it with the claimed one, and
raises explicit flags, each with a plain-English explanation. The score is a
transparent penalty sum (see `score_from_flags`), not a black box, so every
point can be explained to a user.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from statistics import median
from typing import Optional

from ..models import PricePoint, SaleEvent
from .features import active_sale, window

BASELINE_DAYS = 30
HIKE_WINDOW_DAYS = 14
MIN_BASELINE_POINTS = 4
MIN_BASELINE_SPAN_DAYS = 7

HIKE_THRESHOLD_PCT = 8.0        # pre-sale median this far above baseline = hike
GAP_THRESHOLD_PCT = 15.0        # claimed minus real discount, in points
MRP_RAISE_THRESHOLD_PCT = 10.0  # MRP raised by more than this during tracking
CHEAPER_BEFORE_PCT = 5.0        # was this much cheaper in the last 90 days

FLAG_INFLATED_MRP = "inflated_mrp"
FLAG_PRE_SALE_HIKE = "pre_sale_hike"
FLAG_MRP_RAISED = "mrp_raised"
FLAG_FAKE_LOWEST = "fake_lowest_claim"
FLAG_CHEAPER_BEFORE = "cheaper_before"

VERDICT_GENUINE = "genuine"
VERDICT_PARTLY = "partly_inflated"
VERDICT_MISLEADING = "misleading"
VERDICT_INSUFFICIENT = "insufficient_data"


@dataclass
class Flag:
    code: str
    severity: str  # "high" | "medium" | "low"
    message: str
    magnitude: float = 0.0


@dataclass
class HonestyReport:
    verdict: str
    score: Optional[int]
    confidence: str  # "high" | "medium" | "low"
    current_price: float
    currency: str
    baseline_price: Optional[float]
    real_discount_pct: Optional[float]
    claimed_discount_pct: Optional[float]
    mrp: Optional[float]
    sale_name: Optional[str]
    flags: list[Flag] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _money(value: float, currency: str) -> str:
    symbol = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}.get(currency, currency + " ")
    return f"{symbol}{value:,.0f}"


def _confidence(points: list[PricePoint]) -> str:
    if len(points) < MIN_BASELINE_POINTS:
        return "low"
    span = (points[-1].timestamp - points[0].timestamp).days
    if span < MIN_BASELINE_SPAN_DAYS:
        return "low"
    if len(points) >= 10 and span >= 21:
        return "high"
    return "medium"


def score_from_flags(flags: list[Flag]) -> int:
    """100 minus a penalty per flag. Any medium/high flag also caps the score
    at 74, so a listing with a real problem can never be rated "genuine"."""
    penalty = 0.0
    for f in flags:
        if f.code == FLAG_INFLATED_MRP:
            penalty += min(65.0, 10 + f.magnitude * 1.1)
        elif f.code == FLAG_PRE_SALE_HIKE:
            penalty += min(35.0, 10 + f.magnitude * 1.2)
        elif f.code == FLAG_FAKE_LOWEST:
            penalty += 30
        elif f.code == FLAG_MRP_RAISED:
            penalty += 10
        elif f.code == FLAG_CHEAPER_BEFORE:
            penalty += 5
    score = max(0.0, min(100.0, 100 - penalty))
    if any(f.severity in ("high", "medium") for f in flags):
        score = min(score, 74.0)
    return int(round(score))


def _verdict(score: int) -> str:
    if score >= 75:
        return VERDICT_GENUINE
    if score >= 45:
        return VERDICT_PARTLY
    return VERDICT_MISLEADING


def analyze(history: list[PricePoint], sales: list[SaleEvent],
            at: Optional[datetime] = None) -> Optional[HonestyReport]:
    """Judge the latest observation (or the one at `at`) against its own past."""
    past = [p for p in history if at is None or p.timestamp <= at]
    if not past:
        return None
    past.sort(key=lambda p: p.timestamp)
    current = past[-1]
    now = current.timestamp
    cur = current.currency

    sale = active_sale(sales, now)
    anchor = sale.start_dt if sale else now
    hike_start = anchor - timedelta(days=HIKE_WINDOW_DAYS)
    baseline_points = [p for p in window(past, hike_start, BASELINE_DAYS) if p.timestamp < hike_start]
    hike_points = [p for p in past if hike_start <= p.timestamp < anchor]

    confidence = _confidence(baseline_points)
    baseline = median(p.price for p in baseline_points) if baseline_points else None

    claimed = current.claimed_discount_pct
    if claimed is None and current.mrp and current.mrp > current.price:
        claimed = round((current.mrp - current.price) / current.mrp * 100, 1)

    flags: list[Flag] = []

    # Claims that can be checked even with little history.
    recent90 = window(past, now, 90)
    low90 = min(recent90, key=lambda p: p.price)
    if current.deal_badge and "lowest" in current.deal_badge.lower() and current.price > low90.price * 1.01:
        flags.append(Flag(
            FLAG_FAKE_LOWEST, "high",
            f'Labelled "{current.deal_badge}", but it sold for {_money(low90.price, cur)} '
            f"on {low90.timestamp:%d %b}.",
        ))

    mrps = [p.mrp for p in past[:-1] if p.mrp]
    if current.mrp and mrps:
        earliest_mrp = mrps[0]
        raise_pct = (current.mrp - earliest_mrp) / earliest_mrp * 100
        if raise_pct > MRP_RAISE_THRESHOLD_PCT:
            flags.append(Flag(
                FLAG_MRP_RAISED, "medium",
                f"The listed MRP rose from {_money(earliest_mrp, cur)} to {_money(current.mrp, cur)} "
                f"while we tracked it, which makes the discount look bigger.",
                magnitude=round(raise_pct, 1),
            ))

    if baseline is None or confidence == "low":
        return HonestyReport(
            verdict=VERDICT_INSUFFICIENT, score=None, confidence="low",
            current_price=current.price, currency=cur, baseline_price=baseline,
            real_discount_pct=None, claimed_discount_pct=claimed, mrp=current.mrp,
            sale_name=sale.name if sale else None, flags=flags,
            summary="Not enough price history yet to judge this discount. "
                    f"Needs at least {MIN_BASELINE_POINTS} checks over {MIN_BASELINE_SPAN_DAYS}+ days "
                    "before the sale window.",
        )

    real = (baseline - current.price) / baseline * 100

    if hike_points:
        hike_level = median(p.price for p in hike_points)
        hike_pct = (hike_level - baseline) / baseline * 100
        if hike_pct >= HIKE_THRESHOLD_PCT:
            flags.append(Flag(
                FLAG_PRE_SALE_HIKE, "high",
                f"The price was raised about {hike_pct:.0f}% in the {HIKE_WINDOW_DAYS} days before "
                f"{sale.name if sale else 'now'} (from a usual {_money(baseline, cur)} to "
                f"{_money(hike_level, cur)}).",
                magnitude=round(hike_pct, 1),
            ))

    if claimed is not None:
        gap = claimed - max(real, 0.0)
        if gap >= GAP_THRESHOLD_PCT:
            flags.append(Flag(
                FLAG_INFLATED_MRP, "high" if gap >= 30 else "medium",
                f"Advertised as {claimed:.0f}% off, but it's only {max(real, 0):.0f}% below its usual "
                f"price of {_money(baseline, cur)}.",
                magnitude=round(gap, 1),
            ))

    if low90.price < current.price * (1 - CHEAPER_BEFORE_PCT / 100) and not any(
        f.code == FLAG_FAKE_LOWEST for f in flags
    ):
        flags.append(Flag(
            FLAG_CHEAPER_BEFORE, "low",
            f"It was cheaper recently: {_money(low90.price, cur)} on {low90.timestamp:%d %b}.",
            magnitude=round((current.price - low90.price) / current.price * 100, 1),
        ))

    score = score_from_flags(flags)
    verdict = _verdict(score)
    if verdict == VERDICT_GENUINE:
        summary = (f"Real deal: {max(real, 0):.0f}% below its usual price of {_money(baseline, cur)}."
                   if real >= 3 else f"No manipulation detected, but the price is close to its usual "
                                     f"{_money(baseline, cur)}.")
    else:
        label = "Partly inflated" if verdict == VERDICT_PARTLY else "Misleading"
        if claimed is not None and claimed - max(real, 0) >= 5:
            summary = (f"{label}: the real saving is about {max(real, 0):.0f}%, not the advertised "
                       f"{claimed:.0f}%.")
        else:
            summary = (f"{label}: the real saving is about {max(real, 0):.0f}% against its usual price of "
                       f"{_money(baseline, cur)}, and the listing has the issues below.")

    return HonestyReport(
        verdict=verdict, score=score, confidence=confidence,
        current_price=current.price, currency=cur, baseline_price=round(baseline, 2),
        real_discount_pct=round(real, 1), claimed_discount_pct=claimed, mrp=current.mrp,
        sale_name=sale.name if sale else None, flags=flags, summary=summary,
    )
