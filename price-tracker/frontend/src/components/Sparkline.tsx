import { Area, AreaChart, ResponsiveContainer, YAxis } from "recharts";
import type { PricePoint } from "../types";

interface Props {
  history: PricePoint[];
  positive: boolean;
}

export default function Sparkline({ history, positive }: Props) {
  const data = history.length > 0 ? history : [];
  const color = positive ? "#34d399" : "#818cf8";
  const gradientId = `spark-${positive ? "good" : "neutral"}`;

  if (data.length < 2) {
    return (
      <div className="flex h-14 items-center justify-center text-[11px] text-white/25">
        collecting price history…
      </div>
    );
  }

  const prices = data.map((d) => d.price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const pad = (max - min) * 0.15 || max * 0.05 || 1;

  return (
    <ResponsiveContainer width="100%" height={56}>
      <AreaChart data={data} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.35} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <YAxis domain={[min - pad, max + pad]} hide />
        <Area
          type="monotone"
          dataKey="price"
          stroke={color}
          strokeWidth={2}
          fill={`url(#${gradientId})`}
          isAnimationActive={true}
          animationDuration={600}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
