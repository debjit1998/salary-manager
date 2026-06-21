"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatCompact } from "@/lib/format";
import type { HeadcountChangeRow } from "@/types/api";

interface Props {
  rows: HeadcountChangeRow[];
  height?: number;
}

export function HeadcountChangeViz({ rows, height = 280 }: Props) {
  const chartData = rows.map((r) => ({
    dimension: r.dimension,
    "Before period": r.before_start,
    "Hired in period": r.hired_in_period,
  }));
  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>
        <BarChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis dataKey="dimension" stroke="hsl(var(--muted-foreground))" fontSize={11} />
          <YAxis
            stroke="hsl(var(--muted-foreground))"
            fontSize={11}
            tickFormatter={formatCompact}
            width={50}
          />
          <Tooltip
            contentStyle={{
              borderRadius: 8,
              border: "1px solid hsl(var(--border))",
              fontSize: 12,
            }}
            formatter={(v: number) => v.toLocaleString()}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar
            dataKey="Before period"
            stackId="hc"
            fill="hsl(220, 13%, 70%)"
            radius={[0, 0, 0, 0]}
          />
          <Bar
            dataKey="Hired in period"
            stackId="hc"
            fill="hsl(142, 71%, 45%)"
            radius={[4, 4, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
