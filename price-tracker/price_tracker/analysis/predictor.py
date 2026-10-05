"""Buy-now-or-wait recommendation.

Two implementations behind one function:

* A rule-based predictor that works from day one with only a few checks.
* A trained classifier (see train.py) that predicts whether the price will
  drop at least DROP_PCT within HORIZON_DAYS. It is used only when a model
  file exists, and train.py reports how it compares with the rules on a
  held-out time period -- so the ML path has to earn its place.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from ..config import DATA_DIR
from ..models import PricePoint, SaleEvent
from .features import Features, compute_features

logger = logging.getLogger(__name__)

MODEL_PATH = DATA_DIR / "models" / "buy_wait.joblib"
HORIZON_DAYS = 7
DROP_PCT = 3.0
MIN_HISTORY_DAYS_FOR_ML = 14

BUY, WAIT, NEUTRAL = "buy", "wait", "neutral"


@dataclass
class Recommendation:
    action: str        # buy | wait | neutral
    confidence: str    # high | medium | low
    reason: str
    source: str        # rules | model
    drop_probability: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)


def rule_based(f: Features) -> Recommendation:
    conf = "medium" if f.days_tracked >= 14 else "low"
    if f.in_sale and f.pct_above_min_30d <= 2:
        return Recommendation(BUY, conf, "It's at its lowest price in 30 days, during a sale.", "rules")
    if not f.in_sale and f.days_to_next_sale <= 21:
        return Recommendation(
            WAIT, conf,
            f"A sale starts in {f.days_to_next_sale:.0f} days. Prices often drop then, though some "
            "sellers raise them first, so check the honesty score when it starts.", "rules")
    if f.slope_7d_pct_per_day <= -0.5 and f.consecutive_drops >= 3:
        return Recommendation(
            WAIT, conf, f"The price has dropped {f.consecutive_drops:.0f} checks in a row and may keep falling.",
            "rules")
    if f.pct_above_min_30d >= 10 and f.volatility_30d >= 0.04:
        return Recommendation(
            WAIT, conf,
            f"This price swings often, and it was {f.pct_above_min_30d:.0f}% lower in the last 30 days.",
            "rules")
    if f.pct_above_min_30d <= 3:
        return Recommendation(BUY, conf, "It's within 3% of its lowest price in the last 30 days.", "rules")
    return Recommendation(NEUTRAL, "low", "No strong signal either way right now.", "rules")


@lru_cache(maxsize=1)
def _load_model(path: str):
    try:
        import joblib
        return joblib.load(path)
    except Exception as exc:  # pragma: no cover - depends on local files
        logger.warning("Could not load buy/wait model (%s); using rules.", exc)
        return None


def reconcile(rec: Optional[Recommendation], report) -> Optional[Recommendation]:
    """Don't tell someone a deal is a good buy when the honesty engine has
    just shown the discount is mostly marketing."""
    if rec is None or report is None or rec.action != BUY:
        return rec
    if report.verdict in ("partly_inflated", "misleading") and (report.real_discount_pct or 0) < 5:
        usual = f"{report.baseline_price:,.0f}" if report.baseline_price else "its usual level"
        return Recommendation(
            NEUTRAL, rec.confidence,
            f"There's no real discount: the price is about its usual {usual}. "
            "No need to rush; buy only if you need it now.",
            rec.source, rec.drop_probability)
    return rec


def recommend(history: list[PricePoint], sales: list[SaleEvent],
              model_path: Path = MODEL_PATH) -> Optional[Recommendation]:
    features = compute_features(history, sales)
    if features is None:
        return None
    if model_path.exists() and features.days_tracked >= MIN_HISTORY_DAYS_FOR_ML:
        model = _load_model(str(model_path))
        if model is not None:
            prob = float(model.predict_proba([features.vector()])[0][1])
            if prob >= 0.6:
                action, reason = WAIT, f"The model gives a {prob:.0%} chance of a {DROP_PCT:.0f}%+ drop within {HORIZON_DAYS} days."
            elif prob <= 0.35:
                action, reason = BUY, f"The model gives only a {prob:.0%} chance of a meaningful drop within {HORIZON_DAYS} days."
            else:
                action, reason = NEUTRAL, f"The model is unsure ({prob:.0%} chance of a drop within {HORIZON_DAYS} days)."
            conf = "high" if abs(prob - 0.5) >= 0.3 else "medium"
            return Recommendation(action, conf, reason, "model", round(prob, 3))
    return rule_based(features)
