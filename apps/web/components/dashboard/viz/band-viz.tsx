"use client";

import Link from "next/link";

import { CountryFlag } from "@/components/employees/country-flag";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { formatCurrency } from "@/lib/format";
import type { BandSummary, OutOfBandEmployee } from "@/types/api";

interface Props {
  summary: BandSummary;
  list: OutOfBandEmployee[];
  /** When true, only show the summary tiles (compact dashboard panel).
   *  When false, also show the table — used by NL answers. */
  compact?: boolean;
}

export function BandViz({ summary, list, compact = false }: Props) {
  const total = summary.below + summary.within + summary.above;
  const tiles = [
    { label: "Below", value: summary.below, color: "bg-red-50 text-red-700 border-red-200", dot: "bg-red-500" },
    { label: "Within", value: summary.within, color: "bg-emerald-50 text-emerald-700 border-emerald-200", dot: "bg-emerald-500" },
    { label: "Above", value: summary.above, color: "bg-amber-50 text-amber-700 border-amber-200", dot: "bg-amber-500" },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-2">
        {tiles.map((t) => (
          <div
            key={t.label}
            className={cn("rounded-md border p-3", t.color)}
          >
            <div className="flex items-center gap-1.5 text-xs font-medium">
              <span className={cn("inline-block size-1.5 rounded-full", t.dot)} />
              {t.label}
            </div>
            <div className="mt-1 text-xl font-semibold tabular-nums">
              {t.value.toLocaleString()}
            </div>
            <div className="text-xs opacity-70">
              {total > 0 ? `${((t.value / total) * 100).toFixed(1)}%` : "—"}
            </div>
          </div>
        ))}
      </div>

      {!compact && list.length > 0 && (
        <div className="-mx-3 rounded-md border">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Name</TableHead>
                <TableHead>Country</TableHead>
                <TableHead>Level</TableHead>
                <TableHead>Position</TableHead>
                <TableHead className="text-right">Current</TableHead>
                <TableHead className="text-right">Band range</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {list.slice(0, 25).map((r) => (
                <TableRow key={r.id}>
                  <TableCell>
                    <Link
                      href={`/employees/${r.id}`}
                      className="font-medium text-slate-900 hover:text-primary hover:underline"
                    >
                      {r.first_name} {r.last_name}
                    </Link>
                    <div className="text-xs text-muted-foreground">{r.department}</div>
                  </TableCell>
                  <TableCell>
                    <CountryFlag country={r.country} />
                  </TableCell>
                  <TableCell className="font-mono text-xs">{r.level}</TableCell>
                  <TableCell>
                    <span
                      className={cn(
                        "rounded px-1.5 py-0.5 text-xs font-medium",
                        r.band_position === "below"
                          ? "bg-red-100 text-red-700"
                          : "bg-amber-100 text-amber-700",
                      )}
                    >
                      {r.band_position}
                    </span>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatCurrency(Number(r.amount), r.currency_code)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-muted-foreground">
                    {formatCurrency(Number(r.band_min), r.currency_code)}–
                    {formatCurrency(Number(r.band_max), r.currency_code)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {list.length > 25 && (
            <div className="border-t px-3 py-2 text-xs text-muted-foreground">
              Showing 25 of {list.length}.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
