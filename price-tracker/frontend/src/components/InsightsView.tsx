import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarRange, Trash2 } from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import type { SaleEvent } from "../types";

const VERDICT_BAR: Record<string, string> = {
  Genuine: "bg-emerald-400",
  "Partly inflated": "bg-amber-400",
  Misleading: "bg-rose-400",
};

function SaleManager({ sales }: { sales: SaleEvent[] }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["sales"] });
    queryClient.invalidateQueries({ queryKey: ["products"] });
    queryClient.invalidateQueries({ queryKey: ["insights"] });
  };
  const add = useMutation({
    mutationFn: api.addSale,
    onSuccess: () => {
      setName("");
      setStart("");
      setEnd("");
      setError(null);
      refresh();
    },
    onError: (err: any) => setError(err?.response?.data?.detail ?? "Couldn't save the sale window."),
  });
  const remove = useMutation({ mutationFn: api.removeSale, onSuccess: refresh });

  return (
    <section className="glass rounded-2xl p-4">
      <h3 className="flex items-center gap-2 text-[13px] font-semibold text-white/85">
        <CalendarRange className="h-4 w-4 text-white/40" /> Sale windows
      </h3>
      <p className="mt-1 text-[11.5px] text-white/40">
        Prices inside a sale window are judged against the product's usual price from before the sale.
      </p>
      <ul className="mt-3 space-y-1.5">
        {sales.map((s) => (
          <li key={s.id} className="flex items-center justify-between rounded-lg bg-white/[0.03] px-3 py-2 text-[12px]">
            <span>
              <span className="font-medium text-white/80">{s.name}</span>
              <span className="ml-2 text-white/35">
                {new Date(s.start).toLocaleDateString()} to {new Date(s.end).toLocaleDateString()}
              </span>
            </span>
            <button
              onClick={() => remove.mutate(s.id)}
              aria-label={`Remove ${s.name}`}
              className="focus-ring rounded p-1 text-white/30 hover:text-rose-300"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </li>
        ))}
        {sales.length === 0 && <li className="text-[12px] text-white/35">No sale windows yet. Add the next festive sale below.</li>}
      </ul>
      <form
        className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-[1fr_auto_auto_auto]"
        onSubmit={(e) => {
          e.preventDefault();
          add.mutate({ name: name.trim(), start, end });
        }}
      >
        <input
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Sale name, e.g. Diwali Sale"
          aria-label="Sale name"
          className="focus-ring rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-[12.5px] text-white placeholder:text-white/25"
        />
        <input required type="date" value={start} onChange={(e) => setStart(e.target.value)} aria-label="Start date"
          className="focus-ring rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-[12.5px] text-white" />
        <input required type="date" value={end} onChange={(e) => setEnd(e.target.value)} aria-label="End date"
          className="focus-ring rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-[12.5px] text-white" />
        <button type="submit" disabled={add.isPending}
          className="btn-primary focus-ring rounded-lg px-3 py-2 text-[12.5px] font-semibold text-white disabled:opacity-60">
          Add sale
        </button>
      </form>
      {error && <p className="mt-2 text-[12px] text-rose-300">{error}</p>}
    </section>
  );
}

export default function InsightsView({ sales }: { sales: SaleEvent[] }) {
  const [saleId, setSaleId] = useState<string>("");
  const insights = useQuery({
    queryKey: ["insights", saleId],
    queryFn: () => api.insights(saleId || undefined),
    refetchInterval: 30_000,
  });
  const data = insights.data;
  const judged = data?.products_judged ?? 0;
  const notGenuine =
    (data?.verdicts["Misleading"]?.count ?? 0) + (data?.verdicts["Partly inflated"]?.count ?? 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-[17px] font-semibold text-white">Are the sale discounts real?</h2>
          <p className="mt-0.5 text-[12px] text-white/40">
            Every tracked listing, judged against its own price history. The basis for your sale report.
          </p>
        </div>
        <select
          value={saleId}
          onChange={(e) => setSaleId(e.target.value)}
          aria-label="Choose sale"
          className="focus-ring rounded-lg border border-white/10 bg-[#0f1117] px-3 py-2 text-[12.5px] text-white/80"
        >
          <option value="">Latest prices</option>
          {sales.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
      </div>

      {insights.isError && <p className="text-[13px] text-rose-300">Couldn't load insights from the API.</p>}

      {data && judged === 0 && (
        <section className="glass rounded-2xl p-6 text-[13px] text-white/55">
          No listing has enough history to judge yet ({data.products_tracked} tracked). A verdict needs at least
          four checks spread over a week before the sale window, so start tracking early.
        </section>
      )}

      {data && judged > 0 && (
        <>
          <section className="glass rounded-2xl p-5">
            <p className="text-[34px] font-bold leading-none tracking-tight text-white">
              {Math.round((notGenuine / judged) * 100)}%
            </p>
            <p className="mt-2 max-w-xl text-[13px] text-white/60">
              of {judged} judged listings advertised a discount their own price history doesn't support.
              Median advertised discount <b className="text-white/85">{data.median_claimed_discount_pct ?? "—"}%</b>,
              median real discount <b className="text-white/85">{data.median_real_discount_pct ?? "—"}%</b>.
            </p>
            <div className="mt-4 flex h-2.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
              {Object.entries(data.verdicts).map(([label, v]) => (
                <div key={label} className={VERDICT_BAR[label]} style={{ width: `${v.pct ?? 0}%` }} title={`${label}: ${v.count}`} />
              ))}
            </div>
            <div className="mt-2 flex flex-wrap gap-4 text-[11.5px] text-white/50">
              {Object.entries(data.verdicts).map(([label, v]) => (
                <span key={label} className="flex items-center gap-1.5">
                  <span className={`h-2 w-2 rounded-full ${VERDICT_BAR[label]}`} />
                  {label} {v.count}
                </span>
              ))}
              {data.insufficient_history > 0 && <span>Not enough history {data.insufficient_history}</span>}
            </div>
          </section>

          <div className="grid gap-6 lg:grid-cols-2">
            <section className="glass rounded-2xl p-4">
              <h3 className="text-[13px] font-semibold text-white/85">Patterns found</h3>
              <ul className="mt-3 space-y-2.5">
                {Object.entries(data.flags).map(([label, v]) => (
                  <li key={label}>
                    <div className="flex justify-between text-[12px]">
                      <span className="text-white/65">{label}</span>
                      <span className="text-white/45">{v.count} ({v.pct ?? 0}%)</span>
                    </div>
                    <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                      <div className="h-full rounded-full bg-indigo-400/80" style={{ width: `${v.pct ?? 0}%` }} />
                    </div>
                  </li>
                ))}
              </ul>
            </section>

            <section className="glass overflow-x-auto rounded-2xl p-4">
              <h3 className="text-[13px] font-semibold text-white/85">By category</h3>
              <table className="mt-3 w-full text-left text-[12px]">
                <thead className="text-white/35">
                  <tr>
                    <th className="pb-2 font-medium">Category</th>
                    <th className="pb-2 text-right font-medium">Judged</th>
                    <th className="pb-2 text-right font-medium">Not genuine</th>
                    <th className="pb-2 text-right font-medium">Median gap</th>
                  </tr>
                </thead>
                <tbody className="text-white/70">
                  {Object.entries(data.by_category).map(([cat, v]) => (
                    <tr key={cat} className="border-t border-white/5">
                      <td className="py-2">{cat}</td>
                      <td className="py-2 text-right">{v.judged}</td>
                      <td className="py-2 text-right">{v.not_genuine_pct ?? 0}%</td>
                      <td className="py-2 text-right">{v.median_gap_pts} pts</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </div>
        </>
      )}

      <SaleManager sales={sales} />
    </div>
  );
}
