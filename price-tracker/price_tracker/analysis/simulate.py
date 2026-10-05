"""Synthetic price histories with known manipulation patterns.

Used for three things, and never presented as real data:
  * unit tests for the honesty engine,
  * measuring the detector's precision/recall against a known ground truth
    (`python -m price_tracker.cli evaluate`),
  * seeding a demo dashboard (every point is tagged source="simulated").

Each scenario reproduces a pattern that shows up in consumer complaints about
festive sales: an MRP set far above the real selling price, a price raised
shortly before a sale and then "discounted" back, an MRP raised mid-way, and
a "lowest price" badge on a price that was beaten weeks earlier.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from ..models import PricePoint, SaleEvent
from .honesty import (FLAG_FAKE_LOWEST, FLAG_INFLATED_MRP, FLAG_MRP_RAISED,
                      FLAG_PRE_SALE_HIKE)

SCENARIOS = ["genuine", "inflated_mrp", "pre_sale_hike", "mrp_raised", "fake_lowest"]
EXPECTED_FLAGS = {
    "genuine": set(),
    "inflated_mrp": {FLAG_INFLATED_MRP},
    # A pre-sale hike or a raised MRP also inflates the advertised discount,
    # so the inflated-discount flag is a correct (expected) consequence there.
    "pre_sale_hike": {FLAG_PRE_SALE_HIKE, FLAG_INFLATED_MRP},
    "mrp_raised": {FLAG_MRP_RAISED, FLAG_INFLATED_MRP},
    "fake_lowest": {FLAG_FAKE_LOWEST},
}
CATEGORIES = ["Electronics", "Appliances", "Fashion", "Home & Kitchen", "Personal Care"]


@dataclass
class SimulatedListing:
    name: str
    category: str
    scenario: str
    history: list[PricePoint] = field(default_factory=list)

    @property
    def expected_flags(self) -> set[str]:
        return EXPECTED_FLAGS[self.scenario]


def make_sale(start: datetime, days: int = 7, name: str = "Festive Sale") -> SaleEvent:
    return SaleEvent(name=name, start=start.isoformat(), end=(start + timedelta(days=days)).isoformat())


def simulate_listing(scenario: str, sale: SaleEvent, rng: random.Random, *,
                     days_before: int = 60, step_hours: int = 12, noise: float = 0.015,
                     drop_rate: float = 0.0, name: str = "", category: str = "") -> SimulatedListing:
    base = round(rng.uniform(800, 80000), -1)
    start = sale.start_dt - timedelta(days=days_before)
    end = sale.end_dt
    hike_from = sale.start_dt - timedelta(days=12)
    dip_at = sale.start_dt - timedelta(days=35)

    mrp = base * rng.uniform(1.02, 1.08)
    if scenario == "inflated_mrp":
        mrp = base * rng.uniform(1.7, 2.2)
    sale_price = base * rng.uniform(0.75, 0.88)
    if scenario in ("inflated_mrp", "pre_sale_hike", "fake_lowest"):
        sale_price = base * rng.uniform(0.95, 1.0)
    hike_level = base * rng.uniform(1.15, 1.3)
    raised_mrp = base * rng.uniform(1.5, 1.8)

    points: list[PricePoint] = []
    t = start
    while t <= end:
        if drop_rate and rng.random() < drop_rate and t < sale.start_dt:
            t += timedelta(hours=step_hours)  # a missed check (scrape blocked, server down)
            continue
        in_sale = sale.contains(t)
        price = base
        cur_mrp = mrp
        badge = None
        if scenario == "pre_sale_hike" and hike_from <= t < sale.start_dt:
            price = hike_level
        if scenario == "pre_sale_hike":
            cur_mrp = max(mrp, hike_level * 1.05)
        if scenario == "mrp_raised" and t >= sale.start_dt - timedelta(days=20):
            cur_mrp = raised_mrp
        if scenario == "fake_lowest" and abs((t - dip_at).total_seconds()) <= 2 * 86400:
            price = base * 0.8
        if in_sale:
            price = sale_price
            if scenario == "fake_lowest":
                badge = "Lowest price in 30 days"
        price = round(price * (1 + rng.uniform(-noise, noise)), 0)
        claimed = round((cur_mrp - price) / cur_mrp * 100, 1) if cur_mrp > price else None
        points.append(PricePoint(
            price=price, currency="INR", checked_at=t.isoformat(),
            mrp=round(cur_mrp, 0) if cur_mrp > price else None,
            claimed_discount_pct=claimed, deal_badge=badge, source="simulated",
        ))
        t += timedelta(hours=step_hours)
    return SimulatedListing(name or f"Simulated {scenario}", category or rng.choice(CATEGORIES), scenario, points)


def simulate_market(n: int = 100, seed: int = 7, sale_start: datetime | None = None,
                    hard: bool = False) -> tuple[list[SimulatedListing], SaleEvent]:
    """`hard=True` uses 5% price noise, checks every 36h and drops 30% of
    pre-sale checks, to see how the detector degrades with messy data."""
    rng = random.Random(seed)
    sale_start = sale_start or (datetime.now(timezone.utc) - timedelta(days=7)).replace(minute=0, second=0, microsecond=0)
    sale = make_sale(sale_start)
    weights = [0.45, 0.2, 0.15, 0.1, 0.1]
    listings = []
    for i in range(n):
        scenario = rng.choices(SCENARIOS, weights)[0]
        category = rng.choice(CATEGORIES)
        kwargs = dict(noise=0.05, step_hours=36, drop_rate=0.3) if hard else {}
        listings.append(simulate_listing(scenario, sale, rng, name=f"{category} item {i + 1:03d}",
                                         category=category, **kwargs))
    return listings, sale
