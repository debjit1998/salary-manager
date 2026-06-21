import { format, parseISO } from "date-fns";

/** Format a number as a currency. Default USD. */
export function formatCurrency(
  amount: number | string,
  currency = "USD",
  opts: Intl.NumberFormatOptions = {},
): string {
  const num = typeof amount === "string" ? Number(amount) : amount;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
    ...opts,
  }).format(num);
}

/** "Jan 15, 2024" */
export function formatDate(iso: string | Date): string {
  const d = typeof iso === "string" ? parseISO(iso) : iso;
  return format(d, "MMM d, yyyy");
}

/** "1.05" → "1.05x" — for comp ratio display. */
export function formatRatio(n: number | string, digits = 2): string {
  return `${Number(n).toFixed(digits)}x`;
}

/** Shorten large numbers: 1_234_567 → "1.2M". For chart axes / KPI tiles. */
export function formatCompact(n: number): string {
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(n);
}
