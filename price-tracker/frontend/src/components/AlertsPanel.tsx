import { AnimatePresence, motion } from "framer-motion";
import { Bell, Sparkles, TrendingDown } from "lucide-react";
import type { AlertEvent } from "../types";
import { formatMoney, formatRelativeTime, percentChange } from "../utils";

interface Props {
  alerts: AlertEvent[];
}

export default function AlertsPanel({ alerts }: Props) {
  return (
    <div className="glass sticky top-20 rounded-2xl p-4">
      <div className="mb-3 flex items-center gap-2">
        <Bell className="h-4 w-4 text-white/50" />
        <h2 className="text-[13px] font-semibold text-white/90">Alert feed</h2>
        {alerts.length > 0 && (
          <span className="ml-auto rounded-full bg-white/[0.06] px-2 py-0.5 text-[10px] font-medium text-white/50">
            {alerts.length}
          </span>
        )}
      </div>

      {alerts.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 py-8 text-center">
          <Sparkles className="h-5 w-5 text-white/20" />
          <p className="text-[12px] text-white/30">
            No price drops yet.
            <br />
            You'll see them here the instant one happens.
          </p>
        </div>
      ) : (
        <div className="max-h-[60vh] space-y-2 overflow-y-auto pr-1">
          <AnimatePresence initial={false}>
            {alerts.map((a) => {
              const pct = percentChange(a.old_price, a.new_price);
              return (
                <motion.div
                  key={a.id}
                  layout
                  initial={{ opacity: 0, x: 12 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0 }}
                  className="rounded-xl border border-white/5 bg-white/[0.02] p-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="truncate text-[12.5px] font-medium text-white/85">{a.product_name}</p>
                    {a.is_all_time_low && (
                      <span className="shrink-0 rounded-full bg-emerald-400/15 px-1.5 py-0.5 text-[9.5px] font-semibold text-emerald-300">
                        LOW
                      </span>
                    )}
                  </div>
                  <div className="mt-1.5 flex items-center gap-1.5 text-[12px]">
                    <span className="text-white/35 line-through">
                      {formatMoney(a.old_price, a.currency)}
                    </span>
                    <span className="font-semibold text-emerald-300">
                      {formatMoney(a.new_price, a.currency)}
                    </span>
                    <span className="ml-auto flex items-center gap-0.5 rounded bg-emerald-400/10 px-1 py-0.5 text-[10px] font-semibold text-emerald-300">
                      <TrendingDown className="h-2.5 w-2.5" />
                      {Math.abs(pct).toFixed(0)}%
                    </span>
                  </div>
                  <p className="mt-1 text-[10.5px] text-white/25">{formatRelativeTime(a.created_at)}</p>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
