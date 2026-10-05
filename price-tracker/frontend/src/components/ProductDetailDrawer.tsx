import { AnimatePresence, motion } from "framer-motion";
import { ExternalLink, X } from "lucide-react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Product, SaleEvent } from "../types";
import { formatMoney, hostnameOf } from "../utils";
import { ACTION_STYLE, VERDICT_STYLE } from "../verdict";
import HonestyBadge from "./HonestyBadge";

interface Props {
  product: Product | null;
  sales: SaleEvent[];
  onClose: () => void;
}

const SEVERITY_DOT: Record<string, string> = {
  high: "bg-rose-400",
  medium: "bg-amber-400",
  low: "bg-white/40",
};

function ChartTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="rounded-lg border border-white/10 bg-[#0f1117] px-3 py-2 text-[12px] shadow-xl">
      <p className="font-semibold text-white">{formatMoney(point.price, point.currency)}</p>
      {point.mrp && <p className="text-white/45">MRP {formatMoney(point.mrp, point.currency)}</p>}
      {point.deal_badge && <p className="text-amber-300/80">{point.deal_badge}</p>}
      <p className="text-white/40">{new Date(point.checked_at).toLocaleString()}</p>
    </div>
  );
}

export default function ProductDetailDrawer({ product, sales, onClose }: Props) {
  const currency = product?.latest_price?.currency ?? "INR";
  const data = product?.history.map((p) => ({ ...p, t: Date.parse(p.checked_at) })) ?? [];
  const honesty = product?.honesty ?? null;
  const rec = product?.recommendation ?? null;

  return (
    <AnimatePresence>
      {product && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
          />
          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 32, stiffness: 300 }}
            className="fixed right-0 top-0 z-50 h-full w-full max-w-lg overflow-y-auto border-l border-white/10 bg-[#0b0d12] p-6 shadow-2xl"
            role="dialog"
            aria-label={product.name}
          >
            <div className="mb-5 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h2 className="line-clamp-2 text-lg font-bold text-white">{product.name}</h2>
                <a
                  href={product.url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 flex items-center gap-1 text-[12px] text-indigo-300/80 hover:text-indigo-300"
                >
                  {hostnameOf(product.url)} <ExternalLink className="h-3 w-3" />
                </a>
              </div>
              <button
                onClick={onClose}
                aria-label="Close"
                className="focus-ring shrink-0 rounded-lg p-1.5 text-white/40 hover:bg-white/[0.06] hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {honesty && (
              <section className={`mb-5 rounded-xl p-4 ring-1 ${VERDICT_STYLE[honesty.verdict].bg} ${VERDICT_STYLE[honesty.verdict].ring}`}>
                <HonestyBadge honesty={honesty} size="lg" />
                <p className="mt-3 text-[13px] leading-relaxed text-white/80">{honesty.summary}</p>

                {honesty.verdict !== "insufficient_data" && (
                  <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                    <div className="rounded-lg bg-black/20 p-2">
                      <p className="text-[10.5px] text-white/40">Advertised</p>
                      <p className="text-[15px] font-bold text-white">
                        {honesty.claimed_discount_pct != null ? `${honesty.claimed_discount_pct.toFixed(0)}%` : "—"}
                      </p>
                    </div>
                    <div className="rounded-lg bg-black/20 p-2">
                      <p className="text-[10.5px] text-white/40">Real saving</p>
                      <p className="text-[15px] font-bold text-white">
                        {honesty.real_discount_pct != null ? `${Math.max(0, honesty.real_discount_pct).toFixed(0)}%` : "—"}
                      </p>
                    </div>
                    <div className="rounded-lg bg-black/20 p-2">
                      <p className="text-[10.5px] text-white/40">Usual price</p>
                      <p className="text-[15px] font-bold text-white">
                        {honesty.baseline_price != null ? formatMoney(honesty.baseline_price, currency).replace(/\.00$/, "") : "—"}
                      </p>
                    </div>
                  </div>
                )}

                {honesty.flags.length > 0 && (
                  <ul className="mt-4 space-y-2">
                    {honesty.flags.map((f) => (
                      <li key={f.code} className="flex gap-2 text-[12.5px] leading-snug text-white/70">
                        <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${SEVERITY_DOT[f.severity]}`} />
                        {f.message}
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            )}

            {rec && (
              <section className="glass mb-5 rounded-xl p-4">
                <div className="flex items-center justify-between gap-2">
                  <span className={`rounded-md px-2 py-1 text-[12px] font-semibold ${ACTION_STYLE[rec.action].cls}`}>
                    {ACTION_STYLE[rec.action].label}
                  </span>
                  <span className="text-[10.5px] text-white/30">
                    {rec.source === "model" ? "trained model" : "rule-based"}, {rec.confidence} confidence
                  </span>
                </div>
                <p className="mt-2 text-[12.5px] text-white/65">{rec.reason}</p>
              </section>
            )}

            <section className="glass mb-5 rounded-xl p-4">
              <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-white/45">
                <span className="font-medium text-white/60">Price history</span>
                <span className="flex items-center gap-1.5"><span className="h-0.5 w-3 bg-indigo-400" />Price</span>
                <span className="flex items-center gap-1.5"><span className="h-0.5 w-3 border-t border-dashed border-white/50" />MRP</span>
                {honesty?.baseline_price != null && (
                  <span className="flex items-center gap-1.5"><span className="h-0.5 w-3 bg-emerald-400" />Usual price</span>
                )}
                {sales.length > 0 && (
                  <span className="flex items-center gap-1.5"><span className="h-2.5 w-3 rounded-sm bg-amber-300/20" />Sale</span>
                )}
              </div>
              {data.length > 1 ? (
                <ResponsiveContainer width="100%" height={230}>
                  <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                    <defs>
                      <linearGradient id="detail-fill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#818cf8" stopOpacity={0.3} />
                        <stop offset="100%" stopColor="#818cf8" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                    {sales.map((s) => (
                      <ReferenceArea
                        key={s.id}
                        x1={Date.parse(s.start)}
                        x2={Date.parse(s.end)}
                        ifOverflow="hidden"
                        fill="#fcd34d"
                        fillOpacity={0.1}
                      />
                    ))}
                    <XAxis
                      dataKey="t"
                      type="number"
                      scale="time"
                      domain={["dataMin", "dataMax"]}
                      tickFormatter={(v) => new Date(v).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                      tick={{ fill: "rgba(255,255,255,0.35)", fontSize: 10 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      domain={["dataMin - 5%", "dataMax + 5%"]}
                      tick={{ fill: "rgba(255,255,255,0.35)", fontSize: 10 }}
                      axisLine={false}
                      tickLine={false}
                      width={58}
                      tickFormatter={(v) => formatMoney(v, currency).replace(/\.\d\d$/, "")}
                    />
                    <Tooltip content={<ChartTooltip />} />
                    {honesty?.baseline_price != null && (
                      <ReferenceLine y={honesty.baseline_price} stroke="#34d399" strokeOpacity={0.7} />
                    )}
                    <Area type="monotone" dataKey="price" stroke="#818cf8" strokeWidth={2} fill="url(#detail-fill)" />
                    <Line
                      type="stepAfter"
                      dataKey="mrp"
                      stroke="rgba(255,255,255,0.5)"
                      strokeDasharray="4 3"
                      strokeWidth={1.2}
                      dot={false}
                      connectNulls
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              ) : (
                <p className="py-10 text-center text-[12px] text-white/30">
                  Not enough data yet. The chart appears after a couple of price checks.
                </p>
              )}
            </section>

            <section className="glass rounded-xl p-4">
              <p className="mb-3 text-[12px] font-medium text-white/50">All checks ({product.history.length})</p>
              <div className="max-h-64 space-y-1.5 overflow-y-auto pr-1">
                {[...product.history].reverse().map((p, i) => (
                  <div key={i} className="flex items-center justify-between gap-3 rounded-lg bg-white/[0.02] px-3 py-2 text-[12px]">
                    <span className="text-white/40">
                      {new Date(p.checked_at).toLocaleString()}
                      {p.source === "extension" && <span className="ml-1.5 text-sky-300/60">from browser</span>}
                    </span>
                    <span className="text-right">
                      <span className="font-semibold text-white/85">{formatMoney(p.price, p.currency)}</span>
                      {p.mrp && <span className="ml-2 text-white/30 line-through">{formatMoney(p.mrp, p.currency)}</span>}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
