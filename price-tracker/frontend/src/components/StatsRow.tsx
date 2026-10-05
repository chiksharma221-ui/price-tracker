import { motion } from "framer-motion";
import { Bell, PackageSearch, ShieldAlert, TrendingDown } from "lucide-react";
import type { AlertEvent, Product } from "../types";

interface Props {
  products: Product[];
  alerts: AlertEvent[];
}

/** Biggest *real* discount: measured against the product's own usual price,
 *  not the seller's MRP. */
function bestRealDeal(products: Product[]) {
  let best: { pct: number; name: string } | null = null;
  for (const p of products) {
    const real = p.honesty?.real_discount_pct;
    if (real == null || real <= 0 || p.honesty?.verdict !== "genuine") continue;
    if (!best || real > best.pct) best = { pct: real, name: p.name };
  }
  return best;
}

export default function StatsRow({ products, alerts }: Props) {
  const best = bestRealDeal(products);
  const judged = products.filter((p) => p.honesty && p.honesty.verdict !== "insufficient_data");
  const inflated = judged.filter((p) => p.honesty!.verdict !== "genuine").length;

  const stats = [
    {
      label: "Products tracked",
      value: products.length.toString(),
      icon: PackageSearch,
      accent: "from-indigo-400 to-violet-400",
    },
    {
      label: "Inflated discounts",
      value: judged.length ? `${inflated} of ${judged.length}` : "—",
      sub: judged.length ? "listings judged so far" : "needs a week of price history",
      icon: ShieldAlert,
      accent: "from-rose-400 to-orange-400",
    },
    {
      label: "Alerts fired",
      value: alerts.length.toString(),
      icon: Bell,
      accent: "from-fuchsia-400 to-pink-400",
    },
    {
      label: "Best real deal",
      value: best ? `${best.pct.toFixed(0)}% off` : "—",
      sub: best?.name,
      icon: TrendingDown,
      accent: "from-amber-400 to-orange-400",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {stats.map((s, i) => (
        <motion.div
          key={s.label}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.05, duration: 0.3 }}
          className="glass rounded-2xl p-4"
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium uppercase tracking-wide text-white/40">
              {s.label}
            </span>
            <div className={`rounded-lg bg-gradient-to-br ${s.accent} p-1.5 opacity-90`}>
              <s.icon className="h-3.5 w-3.5 text-black/70" strokeWidth={2.5} />
            </div>
          </div>
          <div className="mt-2 text-xl font-bold tracking-tight text-white">{s.value}</div>
          {s.sub && <div className="mt-0.5 truncate text-[11px] text-white/35">{s.sub}</div>}
        </motion.div>
      ))}
    </div>
  );
}
