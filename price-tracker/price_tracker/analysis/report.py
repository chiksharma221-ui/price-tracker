"""Sale-season study: aggregate honesty results across every tracked product
and write a publishable report (Markdown + PNG charts).

Findings are reported by category and pattern, never by seller name: the
data supports "X% of electronics listings in this sample showed a pre-sale
hike", not an accusation against a specific shop.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Optional

from ..models import Product, SaleEvent
from .honesty import (FLAG_CHEAPER_BEFORE, FLAG_FAKE_LOWEST, FLAG_INFLATED_MRP,
                      FLAG_MRP_RAISED, FLAG_PRE_SALE_HIKE, VERDICT_GENUINE,
                      VERDICT_INSUFFICIENT, VERDICT_MISLEADING, VERDICT_PARTLY,
                      HonestyReport, analyze)

FLAG_LABELS = {
    FLAG_INFLATED_MRP: "Advertised discount far above the real one",
    FLAG_PRE_SALE_HIKE: "Price raised shortly before the sale",
    FLAG_MRP_RAISED: "MRP raised during tracking",
    FLAG_FAKE_LOWEST: '"Lowest price" claim contradicted by history',
    FLAG_CHEAPER_BEFORE: "Cheaper earlier in the last 90 days",
}
VERDICT_LABELS = {
    VERDICT_GENUINE: "Genuine",
    VERDICT_PARTLY: "Partly inflated",
    VERDICT_MISLEADING: "Misleading",
}


@dataclass
class Assessed:
    product: Product
    report: HonestyReport


def assess(products: list[Product], sale: Optional[SaleEvent], sales: list[SaleEvent]) -> list[Assessed]:
    """Judge each product at its last observation inside `sale` (or its latest
    observation when no sale is given)."""
    out = []
    for product in products:
        history = product.history
        if sale:
            history = [p for p in history if p.timestamp <= sale.end_dt]
            if not any(sale.contains(p.timestamp) for p in history):
                continue
        if not history:
            continue
        report = analyze(history, sales)
        if report:
            out.append(Assessed(product, report))
    return out


def summarize(assessed: list[Assessed]) -> dict:
    judged = [a for a in assessed if a.report.verdict != VERDICT_INSUFFICIENT]
    n = len(judged)
    verdicts = Counter(a.report.verdict for a in judged)
    flags = Counter(f.code for a in judged for f in a.report.flags)
    with_claim = [a for a in judged if a.report.claimed_discount_pct is not None]

    by_cat: dict[str, list[Assessed]] = defaultdict(list)
    for a in judged:
        by_cat[a.product.category or "Uncategorised"].append(a)

    def pct(k: int, total: int) -> Optional[float]:
        return round(k / total * 100, 1) if total else None

    return {
        "products_tracked": len(assessed),
        "products_judged": n,
        "insufficient_history": len(assessed) - n,
        "verdicts": {VERDICT_LABELS[v]: {"count": verdicts.get(v, 0), "pct": pct(verdicts.get(v, 0), n)}
                     for v in VERDICT_LABELS},
        "flags": {FLAG_LABELS[f]: {"count": flags.get(f, 0), "pct": pct(flags.get(f, 0), n)} for f in FLAG_LABELS},
        "median_claimed_discount_pct": round(median(a.report.claimed_discount_pct for a in with_claim), 1)
        if with_claim else None,
        "median_real_discount_pct": round(median(max(a.report.real_discount_pct, 0) for a in with_claim), 1)
        if with_claim else None,
        "by_category": {
            cat: {
                "judged": len(items),
                "not_genuine_pct": pct(sum(a.report.verdict != VERDICT_GENUINE for a in items), len(items)),
                "median_gap_pts": round(median(
                    (a.report.claimed_discount_pct or 0) - max(a.report.real_discount_pct or 0, 0) for a in items), 1),
            }
            for cat, items in sorted(by_cat.items())
        },
    }


def _charts(assessed: list[Assessed], out_dir: Path) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    judged = [a for a in assessed if a.report.verdict != VERDICT_INSUFFICIENT and a.report.claimed_discount_pct is not None]
    files = []
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    colors = {VERDICT_GENUINE: "#2f9e6e", VERDICT_PARTLY: "#d9a21b", VERDICT_MISLEADING: "#d64545"}

    if judged:
        fig, ax = plt.subplots(figsize=(6.5, 5))
        for verdict, color in colors.items():
            pts = [a for a in judged if a.report.verdict == verdict]
            ax.scatter([max(a.report.real_discount_pct, 0) for a in pts],
                       [a.report.claimed_discount_pct for a in pts],
                       s=22, alpha=0.75, color=color, label=VERDICT_LABELS[verdict])
        lim = max(max(a.report.claimed_discount_pct for a in judged), 10) * 1.05
        ax.plot([0, lim], [0, lim], color="#888", linestyle="--", linewidth=1)
        ax.text(lim * 0.55, lim * 0.5, "claimed = real", color="#888", rotation=38)
        ax.set(xlabel="Real discount vs pre-sale price (%)", ylabel="Advertised discount (%)",
               title="Advertised vs real discount", xlim=(0, lim), ylim=(0, lim))
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(out_dir / "claimed_vs_real.png", dpi=160)
        plt.close(fig)
        files.append("claimed_vs_real.png")

        cats = sorted({a.product.category or "Uncategorised" for a in judged})
        fig, ax = plt.subplots(figsize=(7, 0.55 * len(cats) + 1.5))
        left = [0.0] * len(cats)
        for verdict, color in colors.items():
            shares = []
            for cat in cats:
                items = [a for a in judged if (a.product.category or "Uncategorised") == cat]
                shares.append(sum(a.report.verdict == verdict for a in items) / len(items) * 100)
            ax.barh(cats, shares, left=left, color=color, label=VERDICT_LABELS[verdict])
            left = [l + s for l, s in zip(left, shares)]
        ax.set(xlabel="Share of listings (%)", title="Verdict by category", xlim=(0, 100))
        ax.legend(frameon=False, ncol=3, loc="lower center", bbox_to_anchor=(0.5, -0.45))
        fig.tight_layout()
        fig.savefig(out_dir / "verdicts_by_category.png", dpi=160)
        plt.close(fig)
        files.append("verdicts_by_category.png")

    hiked = [a for a in assessed if any(f.code == FLAG_PRE_SALE_HIKE for f in a.report.flags)]
    if hiked:
        example = max(hiked, key=lambda a: max(f.magnitude for f in a.report.flags if f.code == FLAG_PRE_SALE_HIKE))
        pts = example.product.history
        fig, ax = plt.subplots(figsize=(7, 3.6))
        ax.plot([p.timestamp for p in pts], [p.price for p in pts], color="#3b5bdb", linewidth=1.6, label="Selling price")
        mrps = [(p.timestamp, p.mrp) for p in pts if p.mrp]
        if mrps:
            ax.plot(*zip(*mrps), color="#999", linewidth=1, linestyle="--", label="Listed MRP")
        if example.report.baseline_price:
            ax.axhline(example.report.baseline_price, color="#2f9e6e", linewidth=1, label="Pre-sale usual price")
        ax.set(title=f"Example pre-sale hike ({example.product.category or 'product'})", ylabel="Price (INR)")
        ax.legend(frameon=False, fontsize=8)
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(out_dir / "example_pre_sale_hike.png", dpi=160)
        plt.close(fig)
        files.append("example_pre_sale_hike.png")
    return files


def write_report(products: list[Product], sales: list[SaleEvent], sale: Optional[SaleEvent],
                 out_root: Path, simulated: bool = False) -> Path:
    assessed = assess(products, sale, sales)
    stats = summarize(assessed)
    slug = (sale.name if sale else "latest").lower().replace(" ", "-")
    out_dir = out_root / f"{slug}-{datetime.now(timezone.utc):%Y%m%d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    charts = _charts(assessed, out_dir)

    n = stats["products_judged"]
    lines = [f"# Are festive sale discounts real? {'(SIMULATED DATA)' if simulated else ''}".strip(), ""]
    if simulated:
        lines += ["> **Simulated data.** These numbers come from synthetic listings used to test the "
                  "pipeline. They say nothing about any real marketplace. Do not publish them as findings.", ""]
    if n == 0:
        lines += ["No products had enough history to judge yet.", ""]
    else:
        nm = stats["verdicts"]["Misleading"]["pct"] or 0
        np_ = stats["verdicts"]["Partly inflated"]["pct"] or 0
        lines += [
            "## Headline",
            f"Of **{n} listings** judged{f' during {sale.name}' if sale else ''}, "
            f"**{nm + np_:.0f}%** advertised a discount that our price history did not support "
            f"({nm:.0f}% misleading, {np_:.0f}% partly inflated).",
            "",
            f"Median advertised discount: **{stats['median_claimed_discount_pct']}%**. "
            f"Median real discount against each product's own pre-sale price: "
            f"**{stats['median_real_discount_pct']}%**.",
            "",
            "## What we found",
            "| Pattern | Listings | Share |",
            "|---|---:|---:|",
        ]
        lines += [f"| {label} | {v['count']} | {v['pct']}% |" for label, v in stats["flags"].items()]
        lines += ["", "### By category", "| Category | Judged | Not genuine | Median gap (pts) |", "|---|---:|---:|---:|"]
        lines += [f"| {c} | {v['judged']} | {v['not_genuine_pct']}% | {v['median_gap_pts']} |"
                  for c, v in stats["by_category"].items()]
        lines += [""] + [f"![{c}]({c})" for c in charts] + [""]

    lines += [
        "## Method",
        "- Each listing's price, MRP, advertised discount and deal badges were recorded on a schedule.",
        "- **Usual price** = median selling price over the 30 days ending 14 days before the sale. "
        "The 14 days right before the sale are excluded so a pre-sale hike can't inflate the reference.",
        "- **Real discount** = how far the sale price sits below that usual price.",
        "- A listing is flagged when the advertised discount exceeds the real one by 15+ points, the "
        "price rose 8%+ in the 14 days before the sale, the MRP rose 10%+ during tracking, or a "
        '"lowest price" badge appeared on a price that had been beaten in the previous 90 days.',
        "",
        "## Limitations",
        f"- Sample: {stats['products_tracked']} listings chosen by us, not a random sample of the marketplace.",
        f"- {stats['insufficient_history']} listings lacked enough pre-sale history and were excluded.",
        "- Prices can differ by location, account, bank offer and coupon; we record the default shown price.",
        "- Missed checks (blocked requests, downtime) can hide short price changes.",
        "- Findings describe patterns in this sample, not the conduct of any specific seller.",
    ]
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    import json
    (out_dir / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return out_dir
