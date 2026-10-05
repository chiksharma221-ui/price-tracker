import { AnimatePresence, motion } from "framer-motion";
import { ExternalLink, RefreshCw, Target, Trash2 } from "lucide-react";
import { useState } from "react";
import type { Product } from "../types";
import { formatMoney, formatRelativeTime, hostnameOf, percentChange } from "../utils";
import { ACTION_STYLE } from "../verdict";
import DiscountLine from "./DiscountLine";
import HonestyBadge from "./HonestyBadge";
import Sparkline from "./Sparkline";

interface Props {
  product: Product;
  onOpen: () => void;
  onCheck: () => void;
  onRemove: () => void;
  checking: boolean;
}

export default function ProductCard({ product, onOpen, onCheck, onRemove, checking }: Props) {
  const [confirming, setConfirming] = useState(false);
  const latest = product.latest_price;
  const low = product.all_time_low;
  const isAtLow = !!latest && !!low && latest.price === low.price;
  const change = latest && product.history.length > 1
    ? percentChange(product.history[product.history.length - 2].price, latest.price)
    : 0;

  const targetReached = product.target_price != null && latest != null && latest.price <= product.target_price;
  const targetProgress =
    product.target_price && latest
      ? Math.min(100, (product.target_price / latest.price) * 100)
      : null;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.96 }}
      transition={{ duration: 0.25 }}
      className="glass group relative overflow-hidden rounded-2xl p-4 transition hover:border-white/20"
    >
      {isAtLow && product.history.length > 1 && (
        <span className="absolute right-3 top-3 rounded-full bg-emerald-400/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-300 ring-1 ring-emerald-400/30">
          All-time low
        </span>
      )}

      <button onClick={onOpen} className="block w-full text-left">
        <p className="truncate pr-16 text-[13px] font-semibold text-white/90">{product.name}</p>
        <p className="mt-0.5 text-[11px] text-white/35">
          {hostnameOf(product.url)}
          {product.category && <span className="text-white/25"> · {product.category}</span>}
        </p>

        {product.honesty && (
          <div className="mt-3">
            <HonestyBadge honesty={product.honesty} />
          </div>
        )}

        <div className="mt-3 flex items-end gap-2">
          <span className="text-2xl font-bold tracking-tight text-white">
            {latest ? formatMoney(latest.price, latest.currency) : "—"}
          </span>
          {change !== 0 && (
            <span
              className={`mb-1 rounded px-1.5 py-0.5 text-[11px] font-semibold ${
                change < 0 ? "bg-emerald-400/15 text-emerald-300" : "bg-rose-400/15 text-rose-300"
              }`}
            >
              {change < 0 ? "" : "+"}
              {change.toFixed(1)}%
            </span>
          )}
        </div>

        {latest?.mrp && (
          <p className="mt-0.5 text-[11px] text-white/30">
            MRP <span className="line-through">{formatMoney(latest.mrp, latest.currency)}</span>
          </p>
        )}
        <div className="mt-1">
          <DiscountLine honesty={product.honesty} />
        </div>

        <div className="mt-2">
          <Sparkline history={product.history} positive={change < 0} />
        </div>
      </button>

      {product.target_price != null && (
        <div className="mt-1">
          <div className="mb-1 flex items-center justify-between text-[11px] text-white/40">
            <span className="flex items-center gap-1">
              <Target className="h-3 w-3" /> Target {formatMoney(product.target_price, latest?.currency ?? "INR")}
            </span>
            {targetReached && <span className="font-semibold text-emerald-300">Reached 🎉</span>}
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${targetProgress ?? 0}%` }}
              transition={{ duration: 0.6, ease: "easeOut" }}
              className={`h-full rounded-full ${
                targetReached ? "bg-emerald-400" : "bg-gradient-to-r from-indigo-400 to-fuchsia-400"
              }`}
            />
          </div>
        </div>
      )}

      <div className="mt-3 flex items-center justify-between border-t border-white/5 pt-3">
        <div className="flex min-w-0 items-center gap-2">
          {product.recommendation && (
            <span
              className={`shrink-0 rounded-md px-1.5 py-0.5 text-[10.5px] font-semibold ${
                ACTION_STYLE[product.recommendation.action].cls
              }`}
              title={product.recommendation.reason}
            >
              {ACTION_STYLE[product.recommendation.action].short}
            </span>
          )}
          <span className="truncate text-[10.5px] text-white/25">
            {latest ? formatRelativeTime(latest.checked_at) : "not checked yet"}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <a
            href={product.url}
            target="_blank"
            rel="noreferrer"
            className="focus-ring rounded-lg p-1.5 text-white/35 transition hover:bg-white/[0.06] hover:text-white/80"
            title="Open product page"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
          <button
            onClick={onCheck}
            disabled={checking}
            className="focus-ring rounded-lg p-1.5 text-white/35 transition hover:bg-white/[0.06] hover:text-white/80 disabled:opacity-40"
            title="Check price now"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${checking ? "animate-spin" : ""}`} />
          </button>

          <AnimatePresence mode="wait" initial={false}>
            {confirming ? (
              <motion.div
                key="confirm"
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: "auto" }}
                exit={{ opacity: 0, width: 0 }}
                className="flex items-center gap-1 overflow-hidden whitespace-nowrap"
              >
                <button
                  onClick={onRemove}
                  className="rounded-lg bg-rose-500/20 px-2 py-1 text-[11px] font-semibold text-rose-300 hover:bg-rose-500/30"
                >
                  Remove
                </button>
                <button
                  onClick={() => setConfirming(false)}
                  className="rounded-lg px-2 py-1 text-[11px] text-white/40 hover:text-white/70"
                >
                  Cancel
                </button>
              </motion.div>
            ) : (
              <motion.button
                key="trash"
                onClick={() => setConfirming(true)}
                className="focus-ring rounded-lg p-1.5 text-white/35 transition hover:bg-rose-500/10 hover:text-rose-300"
                title="Stop tracking"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </motion.button>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}
