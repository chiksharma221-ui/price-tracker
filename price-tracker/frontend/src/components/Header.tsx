import { motion } from "framer-motion";
import { Plus, RefreshCw, Tag } from "lucide-react";

export type View = "products" | "insights";

interface Props {
  view: View;
  onViewChange: (view: View) => void;
  onAdd: () => void;
  onCheckAll: () => void;
  checkingAll: boolean;
  lastUpdated: Date | null;
}

export default function Header({ view, onViewChange, onAdd, onCheckAll, checkingAll, lastUpdated }: Props) {
  return (
    <header className="sticky top-0 z-30 border-b border-white/5 bg-[#08090d]/70 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="btn-primary flex h-9 w-9 items-center justify-center rounded-xl shadow-lg shadow-indigo-500/20">
            <Tag className="h-4.5 w-4.5 text-white" strokeWidth={2.5} />
          </div>
          <div>
            <h1 className="text-[15px] font-semibold leading-tight tracking-tight text-white">
              Deal Honesty Tracker
            </h1>
            <p className="flex items-center gap-1.5 text-[11px] text-white/40">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400" />
              </span>
              Live
              {lastUpdated && (
                <span className="text-white/25">
                  · updated {lastUpdated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </span>
              )}
            </p>
          </div>
        </div>

        <nav className="hidden rounded-lg border border-white/10 bg-white/[0.03] p-0.5 sm:flex" aria-label="Views">
          {(["products", "insights"] as View[]).map((v) => (
            <button
              key={v}
              onClick={() => onViewChange(v)}
              aria-current={view === v ? "page" : undefined}
              className={`focus-ring rounded-md px-3 py-1.5 text-[12.5px] font-medium transition ${
                view === v ? "bg-white/[0.09] text-white" : "text-white/45 hover:text-white/80"
              }`}
            >
              {v === "products" ? "Products" : "Sale insights"}
            </button>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <motion.button
            whileTap={{ scale: 0.96 }}
            onClick={onCheckAll}
            disabled={checkingAll}
            className="focus-ring flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-[13px] font-medium text-white/70 transition hover:bg-white/[0.07] hover:text-white disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${checkingAll ? "animate-spin" : ""}`} />
            {checkingAll ? "Checking..." : "Check all"}
          </motion.button>
          <motion.button
            whileTap={{ scale: 0.96 }}
            onClick={onAdd}
            className="btn-primary focus-ring flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-[13px] font-semibold text-white shadow-lg shadow-fuchsia-500/10 transition hover:brightness-110"
          >
            <Plus className="h-3.5 w-3.5" strokeWidth={2.5} />
            Track product
          </motion.button>
        </div>
      </div>
    </header>
  );
}
