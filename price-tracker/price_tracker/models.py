"""Plain data structures shared across the scraper, storage, analysis and API.

Every new field is optional with a safe default, so data written by older
versions of the project (no MRP, no category, no source) still loads.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .urls import canonical_url


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def parse_ts(value: str) -> datetime:
    """Parse an ISO timestamp, treating naive values as UTC."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@dataclass
class PricePoint:
    """One observation of a listing at a moment in time.

    `price` is what the shopper pays. `mrp` is the "original" / strike-through
    price the seller displays next to it -- the number a claimed discount is
    computed from, and the number most often inflated during sales.
    """

    price: float
    currency: str
    checked_at: str = field(default_factory=_now)
    in_stock: bool = True
    mrp: Optional[float] = None
    claimed_discount_pct: Optional[float] = None
    seller: Optional[str] = None
    deal_badge: Optional[str] = None
    source: str = "scraper"  # "scraper" | "extension" | "simulated"

    def to_dict(self) -> dict:
        return {
            "price": self.price,
            "currency": self.currency,
            "checked_at": self.checked_at,
            "in_stock": self.in_stock,
            "mrp": self.mrp,
            "claimed_discount_pct": self.claimed_discount_pct,
            "seller": self.seller,
            "deal_badge": self.deal_badge,
            "source": self.source,
        }

    @staticmethod
    def from_dict(d: dict) -> "PricePoint":
        checked_at = d.get("checked_at", _now())
        if isinstance(checked_at, datetime):  # Mongo time-series returns datetimes
            checked_at = checked_at.replace(tzinfo=checked_at.tzinfo or timezone.utc).isoformat()
        return PricePoint(
            price=d["price"],
            currency=d.get("currency", "INR"),
            checked_at=checked_at,
            in_stock=d.get("in_stock", True),
            mrp=d.get("mrp"),
            claimed_discount_pct=d.get("claimed_discount_pct"),
            seller=d.get("seller"),
            deal_badge=d.get("deal_badge"),
            source=d.get("source", "scraper"),
        )

    @property
    def timestamp(self) -> datetime:
        return parse_ts(self.checked_at)


@dataclass
class Product:
    url: str
    name: str
    target_price: Optional[float] = None
    category: Optional[str] = None
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=_now)
    # Loaded from the observations collection by the store; not persisted on
    # the product document itself (see storage.py for why).
    history: list[PricePoint] = field(default_factory=list)
    last_alert_price: Optional[float] = None

    @property
    def latest_price(self) -> Optional[PricePoint]:
        return self.history[-1] if self.history else None

    @property
    def all_time_low(self) -> Optional[PricePoint]:
        if not self.history:
            return None
        return min(self.history, key=lambda p: p.price)

    def to_dict(self) -> dict:
        """Product document as persisted -- deliberately without history."""
        return {
            "id": self.id,
            "url": self.url,
            "canonical_url": canonical_url(self.url),
            "name": self.name,
            "target_price": self.target_price,
            "category": self.category,
            "created_at": self.created_at,
            "last_alert_price": self.last_alert_price,
        }

    @staticmethod
    def from_dict(d: dict, history: Optional[list[PricePoint]] = None) -> "Product":
        return Product(
            id=d.get("id", new_id()),
            url=d["url"],
            name=d.get("name", d["url"]),
            target_price=d.get("target_price"),
            category=d.get("category"),
            created_at=d.get("created_at", _now()),
            history=history or [],
            last_alert_price=d.get("last_alert_price"),
        )


@dataclass
class SaleEvent:
    """A named sale window, e.g. a festive sale. Used to separate the
    pre-sale baseline from in-sale prices when judging a discount."""

    name: str
    start: str  # ISO date or datetime
    end: str
    id: str = field(default_factory=new_id)

    @property
    def start_dt(self) -> datetime:
        return parse_ts(self.start if "T" in self.start else self.start + "T00:00:00+00:00")

    @property
    def end_dt(self) -> datetime:
        return parse_ts(self.end if "T" in self.end else self.end + "T23:59:59+00:00")

    def contains(self, ts: datetime) -> bool:
        return self.start_dt <= ts <= self.end_dt

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "start": self.start, "end": self.end}

    @staticmethod
    def from_dict(d: dict) -> "SaleEvent":
        return SaleEvent(id=d.get("id", new_id()), name=d["name"], start=d["start"], end=d["end"])


@dataclass
class AlertEvent:
    """A record of one alert that was fired, so the dashboard can show a feed
    of everything that happened -- independent of whether Telegram/email were
    configured to actually deliver it anywhere."""

    product_id: str
    product_name: str
    url: str
    old_price: float
    new_price: float
    currency: str
    is_all_time_low: bool
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "url": self.url,
            "old_price": self.old_price,
            "new_price": self.new_price,
            "currency": self.currency,
            "is_all_time_low": self.is_all_time_low,
            "created_at": self.created_at,
        }

    @staticmethod
    def from_dict(d: dict) -> "AlertEvent":
        return AlertEvent(
            id=d.get("id", new_id()),
            product_id=d["product_id"],
            product_name=d.get("product_name", ""),
            url=d.get("url", ""),
            old_price=d["old_price"],
            new_price=d["new_price"],
            currency=d.get("currency", "INR"),
            is_all_time_low=d.get("is_all_time_low", False),
            created_at=d.get("created_at", _now()),
        )
