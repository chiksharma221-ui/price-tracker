"""Measure the honesty engine against simulated listings with known
manipulation, reporting per-flag precision and recall.

These numbers describe how well the detector recovers patterns it was
designed for on synthetic data. They are a regression test for the logic,
not evidence about real marketplaces.
"""
from __future__ import annotations

from .honesty import (FLAG_FAKE_LOWEST, FLAG_INFLATED_MRP, FLAG_MRP_RAISED,
                      FLAG_PRE_SALE_HIKE, analyze)
from .simulate import simulate_market

EVALUATED_FLAGS = [FLAG_INFLATED_MRP, FLAG_PRE_SALE_HIKE, FLAG_MRP_RAISED, FLAG_FAKE_LOWEST]


def evaluate(n: int = 500, seed: int = 11, hard: bool = False) -> dict:
    listings, sale = simulate_market(n=n, seed=seed, hard=hard)
    counts = {f: {"tp": 0, "fp": 0, "fn": 0} for f in EVALUATED_FLAGS}
    misleading_detected = genuine_cleared = manipulated = genuine = insufficient = 0

    for listing in listings:
        in_sale = [p for p in listing.history if sale.contains(p.timestamp)]
        report = analyze(listing.history, [sale], at=in_sale[-1].timestamp)
        if report.verdict == "insufficient_data":
            insufficient += 1
        found = {f.code for f in report.flags}
        for flag in EVALUATED_FLAGS:
            expected = flag in listing.expected_flags
            hit = flag in found
            if expected and hit:
                counts[flag]["tp"] += 1
            elif hit:
                counts[flag]["fp"] += 1
            elif expected:
                counts[flag]["fn"] += 1
        if listing.expected_flags:
            manipulated += 1
            misleading_detected += report.verdict != "genuine"
        else:
            genuine += 1
            genuine_cleared += report.verdict == "genuine"

    per_flag = {}
    for flag, c in counts.items():
        precision = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else None
        recall = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else None
        per_flag[flag] = {"precision": precision, "recall": recall, **c}
    return {
        "listings": n,
        "mode": "hard (5% noise, 36h checks, 30% missed)" if hard else "standard (1.5% noise, 12h checks)",
        "insufficient_history": insufficient,
        "per_flag": per_flag,
        "manipulated_listings_not_rated_genuine": misleading_detected / manipulated if manipulated else None,
        "genuine_listings_rated_genuine": genuine_cleared / genuine if genuine else None,
        "note": "Synthetic data with known ground truth; not a measurement of real marketplaces.",
    }
