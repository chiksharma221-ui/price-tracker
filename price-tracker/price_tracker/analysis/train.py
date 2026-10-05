"""Train and evaluate the buy-or-wait classifier.

Label: for an observation at time t, did the price fall at least DROP_PCT
below the observed price within the next HORIZON_DAYS? (1 = waiting would
have paid off.)

Evaluation is time-based -- train on the earlier part of the timeline, test
on the later part -- because a random split would let the model peek at the
future of the same products. The model is compared against the rule-based
predictor on the same test rows; if it doesn't beat the rules, keep using
the rules (delete the model file).
"""
from __future__ import annotations

import json
import logging
from datetime import timedelta
from pathlib import Path

from ..models import PricePoint, SaleEvent
from .features import FEATURE_NAMES, compute_features
from .predictor import DROP_PCT, HORIZON_DAYS, MIN_HISTORY_DAYS_FOR_ML, MODEL_PATH, WAIT, rule_based

logger = logging.getLogger(__name__)


def build_dataset(histories: list[list[PricePoint]], sales: list[SaleEvent]):
    rows = []  # (timestamp, features, rule_features, label)
    for history in histories:
        history = sorted(history, key=lambda p: p.timestamp)
        if not history:
            continue
        last_ts = history[-1].timestamp
        for i, point in enumerate(history):
            ts = point.timestamp
            if ts + timedelta(days=HORIZON_DAYS) > last_ts:
                break  # future not fully observed yet
            feats = compute_features(history[: i + 1], sales, at=ts)
            if feats is None or feats.days_tracked < MIN_HISTORY_DAYS_FOR_ML:
                continue
            horizon_end = ts + timedelta(days=HORIZON_DAYS)
            future = [p.price for p in history[i + 1:] if p.timestamp <= horizon_end]
            if not future:
                continue
            label = int(min(future) <= point.price * (1 - DROP_PCT / 100))
            rows.append((ts, feats, label))
    rows.sort(key=lambda r: r[0])
    return rows


def _metrics(y_true: list[int], y_pred: list[int]) -> dict:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
    fp = sum(1 for t, p in zip(y_true, y_pred) if not t and p)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t and not p)
    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "accuracy": round(correct / len(y_true), 3) if y_true else None,
        "precision_wait": round(precision, 3),
        "recall_wait": round(recall, 3),
    }


def train(histories: list[list[PricePoint]], sales: list[SaleEvent],
          model_path: Path = MODEL_PATH, test_fraction: float = 0.25, data_label: str = "store") -> dict:
    from joblib import dump
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score

    rows = build_dataset(histories, sales)
    if len(rows) < 200:
        raise ValueError(f"Only {len(rows)} labelled rows; need at least 200. Track for longer first.")

    split = int(len(rows) * (1 - test_fraction))
    train_rows, test_rows = rows[:split], rows[split:]
    X_train = [r[1].vector() for r in train_rows]
    y_train = [r[2] for r in train_rows]
    X_test = [r[1].vector() for r in test_rows]
    y_test = [r[2] for r in test_rows]
    if len(set(y_train)) < 2:
        raise ValueError("Training data has only one class; can't train a classifier yet.")

    model = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_depth=4, random_state=0)
    model.fit(X_train, y_train)
    proba = model.predict_proba(X_test)[:, 1]
    model_pred = [int(p >= 0.5) for p in proba]
    rules_pred = [int(rule_based(r[1]).action == WAIT) for r in test_rows]

    result = {
        "data": data_label,
        "rows": {"train": len(train_rows), "test": len(test_rows)},
        "test_positive_rate": round(sum(y_test) / len(y_test), 3),
        "split": f"time-based: test = latest {test_fraction:.0%} of observations "
                 f"(from {test_rows[0][0]:%Y-%m-%d})",
        "label": f"price falls >= {DROP_PCT}% within {HORIZON_DAYS} days",
        "features": FEATURE_NAMES,
        "model": {**_metrics(y_test, model_pred),
                  "roc_auc": round(roc_auc_score(y_test, proba), 3) if len(set(y_test)) > 1 else None},
        "rules_baseline": _metrics(y_test, rules_pred),
        "always_buy_baseline": _metrics(y_test, [0] * len(y_test)),
    }
    beats_rules = (result["model"]["accuracy"] or 0) > (result["rules_baseline"]["accuracy"] or 0)
    result["model_beats_rules"] = beats_rules

    model_path.parent.mkdir(parents=True, exist_ok=True)
    if beats_rules:
        dump(model, model_path)
        result["saved_to"] = str(model_path)
    else:
        if model_path.exists():
            model_path.unlink()
        result["saved_to"] = None
    (model_path.parent / "buy_wait_metrics.json").write_text(json.dumps(result, indent=2, default=str))
    return result
