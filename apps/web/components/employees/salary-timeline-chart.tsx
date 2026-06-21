"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatCompact, formatCurrency, formatDate } from "@/lib/format";
import type { SalaryChange } from "@/types/api";

interface Props {
  history: SalaryChange[];
}

const REASON_COLOR: Record<string, string> = {
  hire: "#64748b",
  raise: "#10b981",
  promo: "#6366f1",
  adjustment: "#f59e0b",
};

export function SalaryTimelineChart({ history }: Props) {
  // Recharts wants chronological data
  const data = [...history]
    .sort((a, b) => a.effective_date.localeCompare(b.effective_date))
    .map((c) => ({
      date: c.effective_date,
      amount_usd: Number(c.amount_usd),
      reason: c.reason,
    }));

  if (data.length < 2) {
    return (
      <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
        Not enough history to chart yet.
      </div>
    );
  }

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 16, right: 24, bottom: 8, left: 16 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey="date"
            stroke="hsl(var(--muted-foreground))"
            fontSize={12}
            tickFormatter={(v) => formatDate(v).slice(0, 6)}
          />
          <YAxis
            stroke="hsl(var(--muted-foreground))"
            fontSize={12}
            tickFormatter={(v) => `$${formatCompact(v)}`}
            width={70}
          />
          <Tooltip
            contentStyle={{
              borderRadius: 8,
              border: "1px solid hsl(var(--border))",
              fontSize: 13,
            }}
            formatter={(value: number, _name, entry) => [
              formatCurrency(value),
              entry.payload.reason,
            ]}
            labelFormatter={(label: string) => formatDate(label)}
          />
          <Line
            type="monotone"
            dataKey="amount_usd"
            stroke="hsl(var(--primary))"
            strokeWidth={2}
            dot={(props) => {
              const { cx, cy, payload, index } = props;
              return (
                <circle
                  key={`dot-${index}`}
                  cx={cx}
                  cy={cy}
                  r={4}
                  fill={REASON_COLOR[payload.reason] ?? "hsl(var(--primary))"}
                />
              );
            }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
