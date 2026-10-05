import type { Recommendation, Verdict } from "./types";

export const VERDICT_STYLE: Record<Verdict, { label: string; text: string; bg: string; ring: string; stroke: string }> = {
  genuine: {
    label: "Genuine deal",
    text: "text-emerald-300",
    bg: "bg-emerald-400/10",
    ring: "ring-emerald-400/30",
    stroke: "#34d399",
  },
  partly_inflated: {
    label: "Partly inflated",
    text: "text-amber-300",
    bg: "bg-amber-400/10",
    ring: "ring-amber-400/30",
    stroke: "#fbbf24",
  },
  misleading: {
    label: "Misleading",
    text: "text-rose-300",
    bg: "bg-rose-400/10",
    ring: "ring-rose-400/30",
    stroke: "#fb7185",
  },
  insufficient_data: {
    label: "Learning prices",
    text: "text-white/50",
    bg: "bg-white/[0.04]",
    ring: "ring-white/10",
    stroke: "rgba(255,255,255,0.3)",
  },
};

export const ACTION_STYLE: Record<Recommendation["action"], { label: string; short: string; cls: string }> = {
  buy: { label: "Good time to buy", short: "Buy now", cls: "bg-emerald-400/15 text-emerald-300" },
  wait: { label: "Better to wait", short: "Wait", cls: "bg-sky-400/15 text-sky-300" },
  neutral: { label: "No rush to buy", short: "No rush", cls: "bg-white/[0.06] text-white/50" },
};
