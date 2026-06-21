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

import { formatCompact, formatCurrency } from "@/lib/format";

interface Props {
  data: {
    dimension: string;
    avg_salary_usd: string;
    median_salary_usd: string;
    count: number;
  }[];
  height?: number;
}

export function AvgSalaryViz({ data, height = 280 }: Props) {
  const chartData = data.map((d) => ({
    dimension: d.dimension,
    Average: Number(d.avg_salary_usd),
    Median: Number(d.median_salary_usd),
    count: d.count,
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
            tickFormatter={(v) => `$${formatCompact(v)}`}
            width={70}
          />
          <Tooltip
            contentStyle={{
              borderRadius: 8,
              border: "1px solid hsl(var(--border))",
              fontSize: 12,
            }}
            formatter={(v: number) => formatCurrency(v)}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="Average" fill="hsl(239, 84%, 67%)" radius={[4, 4, 0, 0]} />
          <Bar dataKey="Median" fill="hsl(199, 89%, 48%)" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
