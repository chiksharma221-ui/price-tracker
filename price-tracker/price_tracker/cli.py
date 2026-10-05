"""Command-line interface.

    python -m price_tracker.cli add <url> [--name NAME] [--target-price N]
    python -m price_tracker.cli list
    python -m price_tracker.cli history <product_id>
    python -m price_tracker.cli remove <product_id>
    python -m price_tracker.cli check [<product_id>]   # run a check now, no waiting for the scheduler

Sale-study mode:
    python -m price_tracker.cli import-csv products.csv   # columns: url,name,category,target_price
    python -m price_tracker.cli sale add "Diwali Sale" 2026-10-20 2026-10-27
    python -m price_tracker.cli sale list
    python -m price_tracker.cli honesty <product_id>
    python -m price_tracker.cli report [--sale SALE_ID]
    python -m price_tracker.cli evaluate [--hard]          # detector precision/recall on simulated data
    python -m price_tracker.cli train [--simulated]        # train + evaluate the buy-or-wait model
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path

from .config import BASE_DIR
from .models import Product, SaleEvent
from .scraper import ScrapeError, extract_title, fetch_html, scrape_price
from .storage import get_store
from .tracker import check_all, check_product

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def cmd_add(args: argparse.Namespace) -> None:
    store = get_store()
    name = args.name
    if not name:
        try:
            html = fetch_html(args.url)
            name = extract_title(html, fallback=args.url)
        except ScrapeError:
            name = args.url

    if store.find_product_by_url(args.url):
        print("Already tracking this product.")
        return
    product = Product(url=args.url, name=name, target_price=args.target_price, category=args.category)
    store.add_product(product)
    print(f"Tracking '{product.name}' (id={product.id}) target_price={product.target_price}")

    try:
        check_product(store, product)
        print("Initial price check complete -- run 'list' to see it.")
    except Exception as exc:  # pragma: no cover - best-effort convenience
        print(f"Could not fetch an initial price yet ({exc}). It will be retried by the scheduler.")


def cmd_list(_: argparse.Namespace) -> None:
    store = get_store()
    products = store.list_products()
    if not products:
        print("No products tracked yet. Use 'add <url>' to start.")
        return
    for p in products:
        latest = p.latest_price
        low = p.all_time_low
        price_str = f"{latest.currency} {latest.price:,.2f}" if latest else "no data yet"
        low_str = f" | all-time low: {low.currency} {low.price:,.2f}" if low else ""
        target_str = f" | target: {p.target_price:,.2f}" if p.target_price else ""
        print(f"[{p.id}] {p.name}\n    current: {price_str}{low_str}{target_str}\n    {p.url}")


def cmd_history(args: argparse.Namespace) -> None:
    store = get_store()
    product = store.get_product(args.product_id)
    if not product:
        print(f"No product with id {args.product_id}")
        sys.exit(1)
    print(f"Price history for {product.name}:")
    for point in product.history:
        mrp = f"  MRP {point.mrp:,.0f} ({point.claimed_discount_pct}% off claimed)" if point.mrp else ""
        print(f"  {point.checked_at}  {point.currency} {point.price:,.2f}{mrp}"
              f"  {'(in stock)' if point.in_stock else '(out of stock)'}  [{point.source}]")


def cmd_remove(args: argparse.Namespace) -> None:
    store = get_store()
    removed = store.remove_product(args.product_id)
    print("Removed." if removed else f"No product with id {args.product_id}")


def cmd_check(args: argparse.Namespace) -> None:
    store = get_store()
    if args.product_id:
        product = store.get_product(args.product_id)
        if not product:
            print(f"No product with id {args.product_id}")
            sys.exit(1)
        check_product(store, product)
    else:
        check_all(store)
    print("Check complete.")


def cmd_import_csv(args: argparse.Namespace) -> None:
    store = get_store()
    added = skipped = 0
    with open(args.path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            url = (row.get("url") or "").strip()
            if not url or store.find_product_by_url(url):
                skipped += 1
                continue
            target = row.get("target_price") or None
            store.add_product(Product(url=url, name=(row.get("name") or url).strip(),
                                      category=(row.get("category") or None),
                                      target_price=float(target) if target else None))
            added += 1
    print(f"Added {added} product(s), skipped {skipped} (blank or already tracked).")
    print("Prices will be fetched on the next scheduled run, or run 'check' now.")


def cmd_sale(args: argparse.Namespace) -> None:
    store = get_store()
    if args.action == "add":
        if not (args.name and args.start and args.end):
            sys.exit("Usage: sale add NAME START END   (dates like 2026-10-20)")
        event = SaleEvent(name=args.name, start=args.start, end=args.end)
        store.add_sale_event(event)
        print(f"Added sale '{event.name}' {event.start} -> {event.end} (id={event.id})")
    elif args.action == "list":
        events = store.list_sale_events()
        if not events:
            print("No sale windows yet. Add one with: sale add NAME START END")
        for e in events:
            print(f"[{e.id}] {e.name}: {e.start} -> {e.end}")
    elif args.action == "remove":
        print("Removed." if store.remove_sale_event(args.name or "") else "No sale with that id.")


def cmd_honesty(args: argparse.Namespace) -> None:
    from .analysis.honesty import analyze
    from .analysis.predictor import reconcile, recommend

    store = get_store()
    product = store.get_product(args.product_id)
    if not product:
        sys.exit(f"No product with id {args.product_id}")
    sales = store.list_sale_events()
    report = analyze(product.history, sales)
    rec = reconcile(recommend(product.history, sales), report)
    if report is None:
        sys.exit("No price data yet.")
    print(f"{product.name}\n  Verdict: {report.verdict}  score={report.score}  confidence={report.confidence}")
    print(f"  {report.summary}")
    for flag in report.flags:
        print(f"  - [{flag.severity}] {flag.message}")
    if rec:
        print(f"  Recommendation: {rec.action.upper()} ({rec.source}) - {rec.reason}")


def cmd_report(args: argparse.Namespace) -> None:
    from .analysis.report import write_report

    store = get_store()
    sales = store.list_sale_events()
    sale = next((s for s in sales if s.id == args.sale), None) if args.sale else None
    if args.sale and sale is None:
        sys.exit("No sale with that id. See 'sale list'.")
    products = store.list_products()
    simulated = bool(products) and all(
        p.history and all(pt.source == "simulated" for pt in p.history) for p in products if p.history)
    out = write_report(products, sales, sale, BASE_DIR / "reports", simulated=simulated)
    print(f"Report written to {out / 'report.md'}")


def cmd_evaluate(args: argparse.Namespace) -> None:
    from .analysis.evaluate import evaluate

    print(json.dumps(evaluate(n=args.n, hard=args.hard), indent=2))


def cmd_train(args: argparse.Namespace) -> None:
    from .analysis.train import train

    if args.simulated:
        from .analysis.simulate import simulate_market
        listings, sale = simulate_market(n=200, seed=3, hard=True)
        histories, sales, label = [l.history for l in listings], [sale], "simulated"
    else:
        store = get_store()
        histories = [p.history for p in store.list_products()]
        sales, label = store.list_sale_events(), "store"
    try:
        print(json.dumps(train(histories, sales, data_label=label), indent=2, default=str))
    except ValueError as exc:
        sys.exit(str(exc))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="price_tracker", description="Track e-commerce prices and get alerted on drops.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="Start tracking a product URL")
    p_add.add_argument("url")
    p_add.add_argument("--name", default=None, help="Friendly name (auto-detected from the page if omitted)")
    p_add.add_argument("--target-price", type=float, default=None, help="Alert when the price drops to/below this")
    p_add.add_argument("--category", default=None, help="Category used in sale-season reports")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="List all tracked products")
    p_list.set_defaults(func=cmd_list)

    p_hist = sub.add_parser("history", help="Show price history for one product")
    p_hist.add_argument("product_id")
    p_hist.set_defaults(func=cmd_history)

    p_remove = sub.add_parser("remove", help="Stop tracking a product")
    p_remove.add_argument("product_id")
    p_remove.set_defaults(func=cmd_remove)

    p_check = sub.add_parser("check", help="Run a price check now instead of waiting for the scheduler")
    p_check.add_argument("product_id", nargs="?", default=None)
    p_check.set_defaults(func=cmd_check)

    p_csv = sub.add_parser("import-csv", help="Bulk-add products from a CSV (url,name,category,target_price)")
    p_csv.add_argument("path")
    p_csv.set_defaults(func=cmd_import_csv)

    p_sale = sub.add_parser("sale", help="Manage sale windows: add NAME START END | list | remove ID")
    p_sale.add_argument("action", choices=["add", "list", "remove"])
    p_sale.add_argument("name", nargs="?", default=None)
    p_sale.add_argument("start", nargs="?", default=None)
    p_sale.add_argument("end", nargs="?", default=None)
    p_sale.set_defaults(func=cmd_sale)

    p_hon = sub.add_parser("honesty", help="Show the discount honesty analysis for one product")
    p_hon.add_argument("product_id")
    p_hon.set_defaults(func=cmd_honesty)

    p_rep = sub.add_parser("report", help="Write the sale-season report (Markdown + charts) to reports/")
    p_rep.add_argument("--sale", default=None, help="Sale id to report on (default: latest prices)")
    p_rep.set_defaults(func=cmd_report)

    p_eval = sub.add_parser("evaluate", help="Detector precision/recall on simulated listings")
    p_eval.add_argument("--n", type=int, default=500)
    p_eval.add_argument("--hard", action="store_true", help="Noisy, sparse data")
    p_eval.set_defaults(func=cmd_evaluate)

    p_train = sub.add_parser("train", help="Train and evaluate the buy-or-wait model")
    p_train.add_argument("--simulated", action="store_true", help="Train on simulated data (pipeline check only)")
    p_train.set_defaults(func=cmd_train)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
