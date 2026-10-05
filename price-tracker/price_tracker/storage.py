"""Storage layer.

Uses MongoDB when MONGO_URI is configured and reachable. Otherwise (no URI,
or the connection fails at startup) it falls back transparently to a local
JSON file under data/store.json, so the project runs out of the box with zero
external services, and upgrades to real persistence the moment you point it
at a Mongo instance.

Why price history is its own collection
---------------------------------------
Earlier versions pushed every price check into an array embedded in the
product document. That is simple, but the document grows without bound
(MongoDB caps documents at 16 MB), every read of the product list drags the
full history along, and you can't query across products by time -- which is
exactly what sale-season analysis needs ("every observation between these
dates"). Observations now live in their own collection: a native MongoDB
time-series collection (timeField=checked_at, metaField=product_id), or an
`observations` list in the JSON store. Stores written by older versions are
migrated automatically on startup.
"""
from __future__ import annotations

import json
import logging
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import settings
from .models import AlertEvent, PricePoint, Product, SaleEvent, parse_ts
from .urls import canonical_url

logger = logging.getLogger(__name__)


class Store:
    # products
    def add_product(self, product: Product) -> None: raise NotImplementedError
    def get_product(self, product_id: str) -> Optional[Product]: raise NotImplementedError
    def list_products(self) -> list[Product]: raise NotImplementedError
    def remove_product(self, product_id: str) -> bool: raise NotImplementedError
    def find_product_by_url(self, url: str) -> Optional[Product]: raise NotImplementedError
    def update_last_alert_price(self, product_id: str, price: float) -> None: raise NotImplementedError
    # observations
    def append_price(self, product_id: str, point: PricePoint) -> None: raise NotImplementedError
    def get_history(self, product_id: str) -> list[PricePoint]: raise NotImplementedError
    def list_observations(self, since: Optional[datetime] = None,
                          until: Optional[datetime] = None) -> dict[str, list[PricePoint]]:
        raise NotImplementedError
    # alerts
    def add_alert(self, alert: AlertEvent) -> None: raise NotImplementedError
    def list_alerts(self, limit: int = 50) -> list[AlertEvent]: raise NotImplementedError
    # sale events
    def add_sale_event(self, event: SaleEvent) -> None: raise NotImplementedError
    def list_sale_events(self) -> list[SaleEvent]: raise NotImplementedError
    def remove_sale_event(self, event_id: str) -> bool: raise NotImplementedError


def _in_window(point: PricePoint, since: Optional[datetime], until: Optional[datetime]) -> bool:
    ts = point.timestamp
    return (since is None or ts >= since) and (until is None or ts <= until)


class JsonStore(Store):
    """A small, dependency-free persistence backend for local/demo use."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()
        if not self.path.exists():
            self._write({"products": [], "observations": [], "alerts": [], "sales": []})
        else:
            self._migrate()

    def _migrate(self) -> None:
        with self._lock:
            data = self._read()
            changed = False
            for key in ("alerts", "observations", "sales"):
                if key not in data:
                    data[key] = []
                    changed = True
            for product in data["products"]:
                embedded = product.pop("history", None)
                if embedded:
                    data["observations"].extend({"product_id": product["id"], **pt} for pt in embedded)
                    changed = True
                elif embedded is not None:
                    changed = True
            if changed:
                logger.info("Migrated JSON store to the observations layout.")
                self._write(data)

    def _read(self) -> dict:
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        tmp.replace(self.path)  # atomic on POSIX, so a crash can't truncate the store

    @staticmethod
    def _history_index(data: dict) -> dict[str, list[PricePoint]]:
        index: dict[str, list[PricePoint]] = defaultdict(list)
        for obs in data.get("observations", []):
            index[obs["product_id"]].append(PricePoint.from_dict(obs))
        for points in index.values():
            points.sort(key=lambda p: p.timestamp)
        return index

    # products
    def add_product(self, product: Product) -> None:
        with self._lock:
            data = self._read()
            data["products"].append(product.to_dict())
            self._write(data)

    def get_product(self, product_id: str) -> Optional[Product]:
        data = self._read()
        for p in data["products"]:
            if p["id"] == product_id:
                return Product.from_dict(p, self._history_index(data).get(product_id, []))
        return None

    def list_products(self) -> list[Product]:
        data = self._read()
        index = self._history_index(data)
        return [Product.from_dict(p, index.get(p["id"], [])) for p in data["products"]]

    def find_product_by_url(self, url: str) -> Optional[Product]:
        target = canonical_url(url)
        data = self._read()
        for p in data["products"]:
            if p.get("canonical_url", canonical_url(p["url"])) == target:
                return Product.from_dict(p, self._history_index(data).get(p["id"], []))
        return None

    def remove_product(self, product_id: str) -> bool:
        with self._lock:
            data = self._read()
            before = len(data["products"])
            data["products"] = [p for p in data["products"] if p["id"] != product_id]
            data["observations"] = [o for o in data["observations"] if o["product_id"] != product_id]
            self._write(data)
            return len(data["products"]) < before

    def update_last_alert_price(self, product_id: str, price: float) -> None:
        with self._lock:
            data = self._read()
            for p in data["products"]:
                if p["id"] == product_id:
                    p["last_alert_price"] = price
                    break
            self._write(data)

    # observations
    def append_price(self, product_id: str, point: PricePoint) -> None:
        with self._lock:
            data = self._read()
            data["observations"].append({"product_id": product_id, **point.to_dict()})
            self._write(data)

    def get_history(self, product_id: str) -> list[PricePoint]:
        return self._history_index(self._read()).get(product_id, [])

    def list_observations(self, since=None, until=None) -> dict[str, list[PricePoint]]:
        index = self._history_index(self._read())
        return {pid: [p for p in pts if _in_window(p, since, until)] for pid, pts in index.items()}

    # alerts
    def add_alert(self, alert: AlertEvent) -> None:
        with self._lock:
            data = self._read()
            data["alerts"].append(alert.to_dict())
            self._write(data)

    def list_alerts(self, limit: int = 50) -> list[AlertEvent]:
        alerts = [AlertEvent.from_dict(a) for a in self._read().get("alerts", [])]
        alerts.sort(key=lambda a: a.created_at, reverse=True)
        return alerts[:limit]

    # sale events
    def add_sale_event(self, event: SaleEvent) -> None:
        with self._lock:
            data = self._read()
            data["sales"].append(event.to_dict())
            self._write(data)

    def list_sale_events(self) -> list[SaleEvent]:
        events = [SaleEvent.from_dict(s) for s in self._read().get("sales", [])]
        return sorted(events, key=lambda e: e.start_dt)

    def remove_sale_event(self, event_id: str) -> bool:
        with self._lock:
            data = self._read()
            before = len(data["sales"])
            data["sales"] = [s for s in data["sales"] if s["id"] != event_id]
            self._write(data)
            return len(data["sales"]) < before


class MongoStore(Store):
    """MongoDB-backed persistence. Requires MONGO_URI to be reachable."""

    OBSERVATIONS = "price_observations"

    def __init__(self, uri: str, db_name: str):
        import pymongo  # imported lazily so pymongo is optional at runtime

        self.client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=3000)
        self.client.admin.command("ping")  # fail fast if unreachable
        self.db = self.client[db_name]
        self.products = self.db["products"]
        self.alerts = self.db["alerts"]
        self.sales = self.db["sales"]
        self._ensure_observations_collection()
        self.observations = self.db[self.OBSERVATIONS]
        self.products.create_index("id", unique=True)
        self.products.create_index("canonical_url")
        self._migrate_embedded_history()

    def _ensure_observations_collection(self) -> None:
        if self.OBSERVATIONS in self.db.list_collection_names():
            return
        try:
            self.db.create_collection(
                self.OBSERVATIONS,
                timeseries={"timeField": "checked_at", "metaField": "product_id", "granularity": "hours"},
            )
        except Exception as exc:  # pragma: no cover - older servers without time-series support
            logger.warning("Time-series collection unavailable (%s); using a regular collection.", exc)
            self.db.create_collection(self.OBSERVATIONS)
        self.db[self.OBSERVATIONS].create_index([("product_id", 1), ("checked_at", 1)])

    def _migrate_embedded_history(self) -> None:
        for doc in self.products.find({"history": {"$exists": True}}):
            points = [PricePoint.from_dict(p) for p in doc.get("history", [])]
            if points:
                self.observations.insert_many([self._obs_doc(doc["id"], p) for p in points])
            self.products.update_one({"_id": doc["_id"]}, {"$unset": {"history": ""}})
            logger.info("Migrated %d embedded price points for %s", len(points), doc["id"])

    @staticmethod
    def _obs_doc(product_id: str, point: PricePoint) -> dict:
        doc = point.to_dict()
        doc["checked_at"] = parse_ts(point.checked_at)  # time-series needs a real datetime
        doc["product_id"] = product_id
        return doc

    def _histories(self, product_ids: list[str]) -> dict[str, list[PricePoint]]:
        index: dict[str, list[PricePoint]] = defaultdict(list)
        cursor = self.observations.find({"product_id": {"$in": product_ids}}, {"_id": 0}).sort("checked_at", 1)
        for doc in cursor:
            index[doc["product_id"]].append(PricePoint.from_dict(doc))
        return index

    def add_product(self, product: Product) -> None:
        self.products.insert_one(product.to_dict())

    def get_product(self, product_id: str) -> Optional[Product]:
        doc = self.products.find_one({"id": product_id})
        return Product.from_dict(doc, self.get_history(product_id)) if doc else None

    def list_products(self) -> list[Product]:
        docs = list(self.products.find())
        index = self._histories([d["id"] for d in docs])
        return [Product.from_dict(d, index.get(d["id"], [])) for d in docs]

    def find_product_by_url(self, url: str) -> Optional[Product]:
        doc = self.products.find_one({"canonical_url": canonical_url(url)})
        return Product.from_dict(doc, self.get_history(doc["id"])) if doc else None

    def remove_product(self, product_id: str) -> bool:
        self.observations.delete_many({"product_id": product_id})
        return self.products.delete_one({"id": product_id}).deleted_count > 0

    def update_last_alert_price(self, product_id: str, price: float) -> None:
        self.products.update_one({"id": product_id}, {"$set": {"last_alert_price": price}})

    def append_price(self, product_id: str, point: PricePoint) -> None:
        self.observations.insert_one(self._obs_doc(product_id, point))

    def get_history(self, product_id: str) -> list[PricePoint]:
        return self._histories([product_id]).get(product_id, [])

    def list_observations(self, since=None, until=None) -> dict[str, list[PricePoint]]:
        query: dict = {}
        if since or until:
            query["checked_at"] = {k: v for k, v in (("$gte", since), ("$lte", until)) if v}
        index: dict[str, list[PricePoint]] = defaultdict(list)
        for doc in self.observations.find(query, {"_id": 0}).sort("checked_at", 1):
            index[doc["product_id"]].append(PricePoint.from_dict(doc))
        return dict(index)

    def add_alert(self, alert: AlertEvent) -> None:
        self.alerts.insert_one(alert.to_dict())

    def list_alerts(self, limit: int = 50) -> list[AlertEvent]:
        docs = self.alerts.find().sort("created_at", -1).limit(limit)
        return [AlertEvent.from_dict(doc) for doc in docs]

    def add_sale_event(self, event: SaleEvent) -> None:
        self.sales.insert_one(event.to_dict())

    def list_sale_events(self) -> list[SaleEvent]:
        events = [SaleEvent.from_dict(d) for d in self.sales.find({}, {"_id": 0})]
        return sorted(events, key=lambda e: e.start_dt)

    def remove_sale_event(self, event_id: str) -> bool:
        return self.sales.delete_one({"id": event_id}).deleted_count > 0


def get_store() -> Store:
    if settings.mongo_configured:
        try:
            store = MongoStore(settings.mongo_uri, settings.mongo_db_name)
            logger.info("Connected to MongoDB (%s)", settings.mongo_db_name)
            return store
        except Exception as exc:  # pragma: no cover - depends on external service
            logger.warning("MongoDB configured but unreachable (%s); falling back to JSON store.", exc)
    logger.info("Using local JSON store at %s", settings.json_store_path)
    return JsonStore(settings.json_store_path)
