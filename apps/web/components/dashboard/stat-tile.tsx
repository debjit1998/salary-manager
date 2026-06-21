"use client";

import type { LucideIcon } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface Props {
  label: string;
  value: string;
  hint?: string;
  icon: LucideIcon;
  isLoading?: boolean;
  accent?: "default" | "warning";
}

export function StatTile({
  label,
  value,
  hint,
  icon: Icon,
  isLoading,
  accent = "default",
}: Props) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-slate-500">
          {label}
        </span>
        <Icon
          className={cn(
            "size-4",
            accent === "warning" ? "text-amber-500" : "text-slate-400",
          )}
        />
      </div>
      <div className="mt-2">
        {isLoading ? (
          <Skeleton className="h-7 w-24" />
        ) : (
          <div className="text-2xl font-semibold tabular-nums text-slate-900">
            {value}
          </div>
        )}
        {hint && (
          <div className="text-xs text-muted-foreground">{hint}</div>
        )}
      </div>
    </div>
  );
}
