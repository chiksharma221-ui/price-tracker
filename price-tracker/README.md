# Deal Honesty Tracker

**Is that "60% off" real?** During festive sales, an advertised discount is
measured against the seller's MRP, and the MRP is the number that is easiest
to inflate. Some listings also have their price raised in the weeks before a
sale and then "discounted" back to where it was. Shoppers can't see any of
this from a single product page.

This project tracks product prices over time and judges each discount against
the product's *own* price history instead of the seller's MRP. It gives every
listing a **Deal Honesty Score (0–100)** with a plain-English explanation, a
**buy-now-or-wait** recommendation, and a **sale-season report** that
aggregates findings across categories. A **Chrome extension** shows the
verdict directly on Amazon.in and Flipkart product pages.

```
Advertised: ₹4,999  (MRP ₹12,999, 62% off)
Verdict:    Misleading, score 31/100
            Real saving is about 9%, not the advertised 62%.
            • Price was raised ~18% in the 14 days before the sale
            • Advertised discount is 53 points above the real one
```

## What it does

| Component | What it does |
|---|---|
| **Scraper** | 3-tier fallback (JSON-LD → meta tags → site selectors → regex sweep). Captures selling price **plus MRP, claimed discount, seller and deal badges**. |
| **Discount Truth engine** | Builds a reference price from the median price *before* a pre-sale window, so a pre-sale hike can't poison the baseline. Flags inflated discounts, pre-sale hikes, MRP raised during tracking, and false "lowest price" claims. |
| **Buy-or-wait predictor** | Rule-based from day one; an optional scikit-learn classifier is used only once it beats the rules on a time-based held-out split. |
| **Sale-season study** | Bulk-import products by category, define sale windows, generate a Markdown report with charts. Findings are by category and pattern, never by seller. |
| **Distributed checking** | Redis Queue (RQ) workers with a shared per-domain rate limiter. Falls back to a local thread pool when Redis isn't configured. |
| **Dashboard** | React + TypeScript: honesty badges, claimed-vs-real discount, price history with MRP line and shaded sale windows, insights page. |
| **Chrome extension** | Manifest V3. Reads the price and MRP from the page, sends the observation to your API, and shows the verdict in a panel on the page. |

## Architecture

```
 Chrome extension ──observations──┐
                                  ▼
 Dashboard (React) ◄──REST──► FastAPI ──► Discount Truth engine / predictor
                                  │
                       ┌──────────┴──────────┐
                       ▼                     ▼
               MongoDB (or JSON)     Redis queue ◄── scheduler
                       ▲                     │
                       └──── N × rq workers ◄┘ (per-domain rate limit)
```

Every integration degrades gracefully: with no MongoDB it uses a local JSON
file, with no Redis it checks in-process, and with no Telegram/email it still
records alerts in the dashboard feed.

## How the honesty score works

For the observation being judged:

1. **Anchor** = start of the active sale window (or now, outside a sale).
2. **Hike window** = the 14 days before the anchor.
3. **Baseline** = median price over the 30 days *before* the hike window.
4. **Real discount** = how far the current price is below the baseline.

Flags (each with a severity and an explanation):

| Flag | Raised when |
|---|---|
| Inflated discount | Claimed discount exceeds the real one by ≥ 15 points |
| Pre-sale hike | Median price in the hike window is ≥ 8% above baseline |
| MRP raised | Listed MRP rose > 10% while being tracked |
| False "lowest price" | A "lowest price" badge, but it was cheaper in the last 90 days |
| Cheaper before | It sold ≥ 5% cheaper in the last 90 days |

The score is 100 minus a transparent penalty per flag; any medium/high flag
caps it at 74 so a problematic listing is never rated "genuine". With too
little history (< 4 checks over < 7 days before the window) the engine says
**"not enough data"** instead of guessing.

## Quick start (local, no infrastructure)

```bash
pip install -r requirements.txt
cp .env.example .env                     # everything is optional
uvicorn price_tracker.api:app --reload   # API on :8000, docs at /docs

cd frontend && npm install && npm run dev   # dashboard on :5173
```

To explore the dashboard without waiting for real data:

```bash
python seed_demo.py   # 24 SIMULATED listings, all tagged source="simulated"
```

## Full stack with Docker

```bash
cp .env.example .env
docker compose up --build
```

Starts MongoDB, Redis, the API, the scheduler, two scrape workers and the
dashboard (http://localhost:5173).

## Chrome extension

1. Open `chrome://extensions`, enable **Developer mode**.
2. **Load unpacked** → select the `extension/` folder.
3. In the extension's options, set the API URL (default
   `http://127.0.0.1:8000`) and the API token if you set `API_TOKEN`.
4. Open any Amazon.in or Flipkart product page.

Each visit records a price observation, so browsing also builds history. If
the product is new, the panel says there isn't enough history yet and offers
to start tracking it.

## Running a sale-season study

```bash
# 1. Bulk-add products (CSV columns: url,name,category,target_price)
python -m price_tracker.cli import-csv products.csv

# 2. Define the sale window
python -m price_tracker.cli sale add "Festive Sale 2026" 2026-10-01 2026-10-12

# 3. Keep the scheduler running from well before the sale
python -m price_tracker.scheduler      # or docker compose up

# 4. After the sale
python -m price_tracker.cli report --sale <sale-id>   # writes reports/
```

Start tracking **at least 3–4 weeks before** a sale: the baseline needs
history from before the pre-sale window.

## Other CLI commands

```bash
python -m price_tracker.cli add <url> --category Electronics --target-price 1999
python -m price_tracker.cli list
python -m price_tracker.cli history <id>
python -m price_tracker.cli honesty <id>       # full analysis for one product
python -m price_tracker.cli check              # check everything now
python -m price_tracker.cli evaluate --n 500   # detector check on simulated data
python -m price_tracker.cli train              # train/compare buy-or-wait model
```

## Tests and evaluation

```bash
python -m pytest -q                 # 51 backend tests, fully offline
cd extension && npm ci && npm test  # 8 extension tests (jsdom)
```

CI (GitHub Actions) runs the backend tests, a detector evaluation, the
dashboard build and the extension tests on every push.

**About `evaluate`:** it runs the detector on synthetic listings with known
manipulation patterns. It verifies that the detection logic behaves as
designed. It does **not** measure accuracy on real marketplaces, because the
simulator and the detector share the same definitions. Real-world numbers
only come from tracked data.

## Responsible use

- Scraping is deliberately slow: randomized delays, retry with backoff and a
  minimum interval per site shared across all workers. Check each site's
  terms before tracking at scale.
- Reports describe patterns by category. They don't name or accuse
  individual sellers; a price history alone can't establish intent.
- Simulated data is always tagged and labelled as such in the dashboard and
  in reports.

## Project layout

```
price_tracker/
  scraper.py         price + discount-context extraction
  tracker.py         record observations, alerts, local concurrent checks
  jobs.py            RQ job dispatch          ratelimit.py  per-domain limiter
  storage.py         MongoDB / JSON stores    api.py        FastAPI app
  analysis/
    honesty.py       Discount Truth engine    predictor.py  buy-or-wait
    features.py      shared features          train.py      model training
    report.py        sale-season report       simulate.py   synthetic data
    evaluate.py      detector evaluation
frontend/            React + TypeScript dashboard
extension/           Chrome extension (Manifest V3)
tests/               pytest suite + HTML fixtures
```
