export interface PricePoint {
  price: number;
  currency: string;
  checked_at: string;
  in_stock: boolean;
  mrp: number | null;
  claimed_discount_pct: number | null;
  seller: string | null;
  deal_badge: string | null;
  source: string;
}

export type Verdict = "genuine" | "partly_inflated" | "misleading" | "insufficient_data";

export interface HonestyFlag {
  code: string;
  severity: "high" | "medium" | "low";
  message: string;
  magnitude: number;
}

export interface Honesty {
  verdict: Verdict;
  score: number | null;
  confidence: "high" | "medium" | "low";
  current_price: number;
  currency: string;
  baseline_price: number | null;
  real_discount_pct: number | null;
  claimed_discount_pct: number | null;
  mrp: number | null;
  sale_name: string | null;
  flags: HonestyFlag[];
  summary: string;
}

export interface Recommendation {
  action: "buy" | "wait" | "neutral";
  confidence: "high" | "medium" | "low";
  reason: string;
  source: "rules" | "model";
  drop_probability: number | null;
}

export interface Product {
  id: string;
  url: string;
  name: string;
  category: string | null;
  target_price: number | null;
  created_at: string;
  latest_price: PricePoint | null;
  all_time_low: PricePoint | null;
  history: PricePoint[];
  honesty: Honesty | null;
  recommendation: Recommendation | null;
}

export interface AlertEvent {
  id: string;
  product_id: string;
  product_name: string;
  url: string;
  old_price: number;
  new_price: number;
  currency: string;
  is_all_time_low: boolean;
  created_at: string;
}

export interface ProductCreate {
  url: string;
  name?: string;
  category?: string;
  target_price?: number;
}

export interface SaleEvent {
  id: string;
  name: string;
  start: string;
  end: string;
}

export interface CountPct {
  count: number;
  pct: number | null;
}

export interface Insights {
  sale: SaleEvent | null;
  products_tracked: number;
  products_judged: number;
  insufficient_history: number;
  verdicts: Record<string, CountPct>;
  flags: Record<string, CountPct>;
  median_claimed_discount_pct: number | null;
  median_real_discount_pct: number | null;
  by_category: Record<string, { judged: number; not_genuine_pct: number | null; median_gap_pts: number }>;
}
