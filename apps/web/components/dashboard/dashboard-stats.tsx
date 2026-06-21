"use client";

import { AlertTriangle, DollarSign, UserPlus, Users } from "lucide-react";

import { useSummary } from "@/lib/hooks/use-analytics";
import { formatCompact, formatCurrency } from "@/lib/format";

import { StatTile } from "./stat-tile";

export function DashboardStats() {
  const { data, isLoading } = useSummary();
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <StatTile
        label="Active headcount"
        value={data ? data.active_headcount.toLocaleString() : "—"}
        icon={Users}
        isLoading={isLoading}
      />
      <StatTile
        label="Average salary"
        value={
          data
            ? formatCurrency(Number(data.avg_salary_usd))
            : "—"
        }
        hint="annual, USD"
        icon={DollarSign}
        isLoading={isLoading}
      />
      <StatTile
        label="Below band"
        value={data ? data.below_band_count.toLocaleString() : "—"}
        hint={
          data
            ? `${((data.below_band_count / Math.max(1, data.active_headcount)) * 100).toFixed(1)}% of org`
            : undefined
        }
        icon={AlertTriangle}
        isLoading={isLoading}
        accent="warning"
      />
      <StatTile
        label="Hires"
        value={data ? formatCompact(data.hires_last_90_days) : "—"}
        hint="last 90 days"
        icon={UserPlus}
        isLoading={isLoading}
      />
    </div>
  );
}
