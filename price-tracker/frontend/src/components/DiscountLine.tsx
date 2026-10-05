import type { Honesty } from "../types";

/** "Claims 62% off, really 3%" -- the core finding, in one line. */
export default function DiscountLine({ honesty }: { honesty: Honesty | null }) {
  if (!honesty || honesty.claimed_discount_pct == null) return null;
  const claimed = honesty.claimed_discount_pct;
  const real = honesty.real_discount_pct;
  const gap = real == null ? 0 : claimed - Math.max(real, 0);

  return (
    <p className="text-[11.5px] text-white/45">
      Claims <span className="font-semibold text-white/75">{claimed.toFixed(0)}% off</span>
      {real != null && (
        <>
          {", really "}
          <span className={`font-semibold ${gap >= 15 ? "text-rose-300" : "text-emerald-300"}`}>
            {Math.max(real, 0).toFixed(0)}%
          </span>
        </>
      )}
    </p>
  );
}
