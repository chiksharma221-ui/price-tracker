"""FastAPI layer for the dashboard and the Chrome extension.

Run with:
    uvicorn price_tracker.api:app --reload --port 8000
"""
from __future__ import annotations

import time
from datetime import timedelta
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, HttpUrl

from .analysis.honesty import analyze
from .analysis.predictor import recommend, reconcile
from .analysis.report import assess, summarize
from .config import settings
from .jobs import dispatch_all
from .models import PricePoint, Product, SaleEvent
from .scraper import ScrapeError, extract_title, fetch_html
from .storage import JsonStore, Store, get_store
from .tracker import check_product, record_observation

app = FastAPI(title="Deal Honesty Tracker API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_origin_regex=r"chrome-extension://[a-p]{32}",
    allow_methods=["*"],
    allow_headers=["*"],
)

_store: Optional[Store] = None
_sales_cache: tuple[float, list[SaleEvent]] = (0.0, [])
EXTENSION_DEDUP = timedelta(minutes=30)


def get_db() -> Store:
    global _store
    if _store is None:
        _store = get_store()
    return _store


def get_sales() -> list[SaleEvent]:
    global _sales_cache
    if time.monotonic() - _sales_cache[0] > 30:
        _sales_cache = (time.monotonic(), get_db().list_sale_events())
    return _sales_cache[1]


def require_token(x_api_token: Optional[str] = Header(default=None)) -> None:
    if settings.api_token and x_api_token != settings.api_token:
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Token header.")


# --- Schemas -----------------------------------------------------------------

class ProductCreate(BaseModel):
    url: HttpUrl
    name: Optional[str] = None
    category: Optional[str] = None
    target_price: Optional[float] = Field(default=None, ge=0)


class BulkCreate(BaseModel):
    items: list[ProductCreate] = Field(min_length=1, max_length=500)


class PricePointOut(BaseModel):
    price: float
    currency: str
    checked_at: str
    in_stock: bool
    mrp: Optional[float] = None
    claimed_discount_pct: Optional[float] = None
    seller: Optional[str] = None
    deal_badge: Optional[str] = None
    source: str = "scraper"


class FlagOut(BaseModel):
    code: str
    severity: str
    message: str
    magnitude: float


class HonestyOut(BaseModel):
    verdict: str
    score: Optional[int]
    confidence: str
    current_price: float
    currency: str
    baseline_price: Optional[float]
    real_discount_pct: Optional[float]
    claimed_discount_pct: Optional[float]
    mrp: Optional[float]
    sale_name: Optional[str]
    flags: list[FlagOut]
    summary: str


class RecommendationOut(BaseModel):
    action: str
    confidence: str
    reason: str
    source: str
    drop_probability: Optional[float] = None


class ProductOut(BaseModel):
    id: str
    url: str
    name: str
    category: Optional[str]
    target_price: Optional[float]
    created_at: str
    latest_price: Optional[PricePointOut]
    all_time_low: Optional[PricePointOut]
    history: list[PricePointOut]
    honesty: Optional[HonestyOut]
    recommendation: Optional[RecommendationOut]


class AlertOut(BaseModel):
    id: str
    product_id: str
    product_name: str
    url: str
    old_price: float
    new_price: float
    currency: str
    is_all_time_low: bool
    created_at: str


class SaleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    start: str
    end: str


class SaleOut(SaleCreate):
    id: str


class ObservationIn(BaseModel):
    """What the Chrome extension reads from a product page it is showing."""
    url: HttpUrl
    name: str = Field(min_length=1, max_length=300)
    price: float = Field(gt=0)
    currency: str = "INR"
    mrp: Optional[float] = Field(default=None, gt=0)
    claimed_discount_pct: Optional[float] = Field(default=None, ge=0, le=100)
    seller: Optional[str] = Field(default=None, max_length=120)
    deal_badge: Optional[str] = Field(default=None, max_length=120)
    in_stock: bool = True
    category: Optional[str] = None


class AnalysisOut(BaseModel):
    product_id: Optional[str]
    tracked: bool
    tracked_since: Optional[str]
    observations: int
    honesty: Optional[HonestyOut]
    recommendation: Optional[RecommendationOut]


# --- Serialisation --------------------------------------------------------

def _point(p: Optional[PricePoint]) -> Optional[PricePointOut]:
    return PricePointOut(**p.to_dict()) if p else None


def _analysis(product: Product) -> tuple[Optional[HonestyOut], Optional[RecommendationOut]]:
    sales = get_sales()
    report = analyze(product.history, sales)
    rec = reconcile(recommend(product.history, sales), report)
    return (HonestyOut(**report.to_dict()) if report else None,
            RecommendationOut(**rec.to_dict()) if rec else None)


def _product(p: Product) -> ProductOut:
    honesty, rec = _analysis(p)
    return ProductOut(
        id=p.id, url=p.url, name=p.name, category=p.category, target_price=p.target_price,
        created_at=p.created_at, latest_price=_point(p.latest_price), all_time_low=_point(p.all_time_low),
        history=[_point(pt) for pt in p.history], honesty=honesty, recommendation=rec,
    )


def _analysis_out(product: Optional[Product]) -> AnalysisOut:
    if product is None:
        return AnalysisOut(product_id=None, tracked=False, tracked_since=None, observations=0,
                           honesty=None, recommendation=None)
    honesty, rec = _analysis(product)
    return AnalysisOut(product_id=product.id, tracked=True, tracked_since=product.created_at,
                       observations=len(product.history), honesty=honesty, recommendation=rec)


# --- Routes: products ------------------------------------------------------

@app.get("/api/health")
def health():
    store = get_db()
    return {
        "status": "ok",
        "store": "json" if isinstance(store, JsonStore) else "mongodb",
        "queue": "redis" if settings.redis_configured else "local",
        "auth_required": bool(settings.api_token),
    }


@app.get("/api/products", response_model=list[ProductOut])
def list_products():
    return [_product(p) for p in get_db().list_products()]


@app.post("/api/products", response_model=ProductOut, status_code=201, dependencies=[Depends(require_token)])
def add_product(payload: ProductCreate):
    store = get_db()
    url = str(payload.url)
    if store.find_product_by_url(url):
        raise HTTPException(status_code=409, detail="This product is already being tracked.")
    name = payload.name
    if not name:
        try:
            name = extract_title(fetch_html(url), fallback=url)
        except ScrapeError:
            name = url
    product = Product(url=url, name=name, target_price=payload.target_price, category=payload.category)
    store.add_product(product)
    check_product(store, product)  # first check inline so the user sees a price immediately
    return _product(store.get_product(product.id))


@app.post("/api/products/bulk", status_code=202, dependencies=[Depends(require_token)])
def add_products_bulk(payload: BulkCreate, background: BackgroundTasks):
    """Add many products at once (sale-study mode). Prices are fetched in the
    background so the request returns immediately."""
    store = get_db()
    created, skipped = [], 0
    for item in payload.items:
        url = str(item.url)
        if store.find_product_by_url(url):
            skipped += 1
            continue
        product = Product(url=url, name=item.name or url, category=item.category, target_price=item.target_price)
        store.add_product(product)
        created.append(product.id)
    if created:
        background.add_task(dispatch_all, store)
    return {"created": len(created), "skipped_duplicates": skipped}


@app.delete("/api/products/{product_id}", status_code=204, dependencies=[Depends(require_token)])
def remove_product(product_id: str):
    if not get_db().remove_product(product_id):
        raise HTTPException(status_code=404, detail="Product not found")


@app.get("/api/products/{product_id}", response_model=ProductOut)
def get_product(product_id: str):
    product = get_db().get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return _product(product)


@app.post("/api/products/{product_id}/check", response_model=ProductOut, dependencies=[Depends(require_token)])
def check_one(product_id: str):
    store = get_db()
    product = store.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    check_product(store, product)
    return _product(store.get_product(product_id))


@app.post("/api/check-all", dependencies=[Depends(require_token)])
def check_all_products():
    return dispatch_all(get_db())


@app.get("/api/alerts", response_model=list[AlertOut])
def list_alerts(limit: int = 50):
    return [AlertOut(**a.to_dict()) for a in get_db().list_alerts(limit=limit)]


# --- Routes: sale events and insights ------------------------------------

@app.get("/api/sales", response_model=list[SaleOut])
def list_sales():
    return [SaleOut(**s.to_dict()) for s in get_db().list_sale_events()]


@app.post("/api/sales", response_model=SaleOut, status_code=201, dependencies=[Depends(require_token)])
def add_sale(payload: SaleCreate):
    event = SaleEvent(name=payload.name, start=payload.start, end=payload.end)
    try:
        if event.end_dt <= event.start_dt:
            raise HTTPException(status_code=422, detail="The sale must end after it starts.")
    except ValueError:
        raise HTTPException(status_code=422, detail="Use ISO dates, e.g. 2026-10-20.")
    get_db().add_sale_event(event)
    global _sales_cache
    _sales_cache = (0.0, [])
    return SaleOut(**event.to_dict())


@app.delete("/api/sales/{sale_id}", status_code=204, dependencies=[Depends(require_token)])
def remove_sale(sale_id: str):
    if not get_db().remove_sale_event(sale_id):
        raise HTTPException(status_code=404, detail="Sale not found")
    global _sales_cache
    _sales_cache = (0.0, [])


@app.get("/api/insights")
def insights(sale_id: Optional[str] = None):
    sales = get_sales()
    sale = next((s for s in sales if s.id == sale_id), None) if sale_id else None
    if sale_id and sale is None:
        raise HTTPException(status_code=404, detail="Sale not found")
    stats = summarize(assess(get_db().list_products(), sale, sales))
    return {"sale": sale.to_dict() if sale else None, **stats}


# --- Routes: Chrome extension ------------------------------------------

@app.get("/api/lookup", response_model=AnalysisOut)
def lookup(url: str):
    """Analysis for a URL without recording anything."""
    return _analysis_out(get_db().find_product_by_url(url))


@app.post("/api/observations", response_model=AnalysisOut, dependencies=[Depends(require_token)])
def add_observation(obs: ObservationIn):
    """Record what a shopper's browser is showing right now, start tracking
    the product if it's new, and return the honesty analysis.

    The extension reads the page the user already loaded, so these
    observations reflect what a real shopper sees and cost the site nothing
    extra. Repeated identical reports within 30 minutes are ignored.
    """
    store = get_db()
    url = str(obs.url)
    product = store.find_product_by_url(url)
    if product is None:
        product = Product(url=url, name=obs.name.strip(), category=obs.category)
        store.add_product(product)

    latest = product.latest_price
    point = PricePoint(
        price=obs.price, currency=obs.currency, in_stock=obs.in_stock, mrp=obs.mrp,
        claimed_discount_pct=obs.claimed_discount_pct, seller=obs.seller,
        deal_badge=obs.deal_badge, source="extension",
    )
    duplicate = (latest is not None and latest.price == point.price and latest.mrp == point.mrp
                 and point.timestamp - latest.timestamp < EXTENSION_DEDUP)
    if not duplicate:
        record_observation(store, product, point)
    return _analysis_out(product)
