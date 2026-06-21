"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatCompact } from "@/lib/format";

interface Row {
  dimension: string;
  count: number;
}

interface Props {
  data: Row[];
  /** "horizontal" = bars run left-to-right, dim on Y axis (best for
   *  long labels like department names). "vertical" = bars run
   *  bottom-to-top, dim on X (best for short labels like L1..L7). */
  layout?: "horizontal" | "vertical";
  height?: number;
}

// The 8 colors of the rainbow + slate. Repeats if there are more
// categories — fine for our small dimensions (≤8 entries each).
const PALETTE = [
  "hsl(239, 84%, 67%)",
  "hsl(217, 91%, 60%)",
  "hsl(199, 89%, 48%)",
  "hsl(173, 80%, 40%)",
  "hsl(142, 71%, 45%)",
  "hsl(43, 96%, 56%)",
  "hsl(25, 95%, 53%)",
  "hsl(348, 83%, 56%)",
];

export function HeadcountViz({ data, layout = "horizontal", height = 280 }: Props) {
  return layout === "horizontal" ? (
    <HorizontalBars data={data} height={height} />
  ) : (
    <VerticalBars data={data} height={height} />
  );
}

function HorizontalBars({ data, height }: { data: Row[]; height: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 8, right: 16, bottom: 8, left: 8 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          type="number"
          stroke="hsl(var(--muted-foreground))"
          fontSize={11}
          tickFormatter={formatCompact}
        />
        <YAxis
          type="category"
          dataKey="dimension"
          stroke="hsl(var(--muted-foreground))"
          fontSize={11}
          width={120}
        />
        <Tooltip
          contentStyle={{
            borderRadius: 8,
            border: "1px solid hsl(var(--border))",
            fontSize: 12,
          }}
          formatter={(v: number) => [v.toLocaleString(), "Count"]}
        />
        <Bar dataKey="count" radius={[0, 4, 4, 0]}>
          {data.map((_, i) => (
            <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function VerticalBars({ data, height }: { data: Row[]; height: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        data={data}
        margin={{ top: 8, right: 16, bottom: 8, left: 8 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          dataKey="dimension"
          stroke="hsl(var(--muted-foreground))"
          fontSize={11}
        />
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
          formatter={(v: number) => [v.toLocaleString(), "Count"]}
        />
        <Bar dataKey="count" radius={[4, 4, 0, 0]}>
          {data.map((_, i) => (
            <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
