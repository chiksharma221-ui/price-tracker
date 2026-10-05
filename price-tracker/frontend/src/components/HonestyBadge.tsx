import type { Honesty } from "../types";
import { VERDICT_STYLE } from "../verdict";

interface Props {
  honesty: Honesty | null;
  size?: "sm" | "lg";
}

/** Score ring + verdict label. The ring fills to the honesty score. */
export default function HonestyBadge({ honesty, size = "sm" }: Props) {
  if (!honesty) return null;
  const style = VERDICT_STYLE[honesty.verdict];
  const dim = size === "lg" ? 56 : 30;
  const stroke = size === "lg" ? 5 : 3.5;
  const r = (dim - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const filled = honesty.score == null ? 0 : (honesty.score / 100) * circ;

  return (
    <div className="flex items-center gap-2" title={honesty.summary}>
      <div className="relative shrink-0" style={{ width: dim, height: dim }}>
        <svg width={dim} height={dim} className="-rotate-90" aria-hidden="true">
          <circle cx={dim / 2} cy={dim / 2} r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={stroke} />
          <circle
            cx={dim / 2}
            cy={dim / 2}
            r={r}
            fill="none"
            stroke={style.stroke}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${filled} ${circ}`}
          />
        </svg>
        <span
          className={`absolute inset-0 flex items-center justify-center font-bold ${style.text} ${
            size === "lg" ? "text-[15px]" : "text-[10px]"
          }`}
        >
          {honesty.score ?? "?"}
        </span>
      </div>
      <div className="min-w-0">
        <p className={`font-semibold leading-tight ${style.text} ${size === "lg" ? "text-[15px]" : "text-[11.5px]"}`}>
          {style.label}
        </p>
        {size === "lg" ? (
          <p className="mt-0.5 text-[11px] text-white/40">Honesty score, {honesty.confidence} confidence</p>
        ) : (
          <p className="text-[10.5px] text-white/35">honesty score</p>
        )}
      </div>
    </div>
  );
}
