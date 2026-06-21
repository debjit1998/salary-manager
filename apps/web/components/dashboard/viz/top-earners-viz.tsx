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
import { formatCurrency } from "@/lib/format";
import type { TopEarner } from "@/types/api";

interface Props {
  rows: TopEarner[];
  /** If set, each row's amount_target is rendered as the primary
   *  amount and native/USD become the subtitle. Used by NL responses
   *  where the user asked for amounts in a specific currency. */
  targetCurrency?: string;
}

export function TopEarnersViz({ rows, targetCurrency }: Props) {
  if (rows.length === 0) {
    return <p className="py-6 text-center text-sm text-muted-foreground">No earners match.</p>;
  }
  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="w-10 text-right">#</TableHead>
          <TableHead>Name</TableHead>
          <TableHead>Country</TableHead>
          <TableHead>Level</TableHead>
          <TableHead className="text-right">Salary</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r, i) => (
          <TableRow key={r.id}>
            <TableCell className="text-right text-xs tabular-nums text-muted-foreground">
              {i + 1}
            </TableCell>
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
            <TableCell className="text-right tabular-nums">
              {targetCurrency && r.amount_target ? (
                <>
                  <div>
                    {formatCurrency(Number(r.amount_target), targetCurrency)}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    native:{" "}
                    {formatCurrency(Number(r.amount_native), r.currency_code)}
                  </div>
                </>
              ) : (
                <>
                  <div>
                    {formatCurrency(Number(r.amount_native), r.currency_code)}
                  </div>
                  {r.currency_code !== "USD" && (
                    <div className="text-xs text-muted-foreground">
                      ≈ {formatCurrency(Number(r.amount_usd))}
                    </div>
                  )}
                </>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
