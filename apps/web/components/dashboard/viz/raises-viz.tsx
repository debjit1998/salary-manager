"use client";

import Link from "next/link";

import { CountryFlag } from "@/components/employees/country-flag";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatCurrency, formatDate } from "@/lib/format";
import type { RaiseEvent } from "@/types/api";

interface Props {
  rows: RaiseEvent[];
}

const REASON_VARIANT: Record<string, "success" | "default" | "warning"> = {
  raise: "success",
  promo: "default",
  adjustment: "warning",
};

export function RaisesViz({ rows }: Props) {
  if (rows.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-muted-foreground">
        No raises or promotions in this period.
      </p>
    );
  }
  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead>Date</TableHead>
          <TableHead>Name</TableHead>
          <TableHead>Country</TableHead>
          <TableHead>Reason</TableHead>
          <TableHead className="text-right">Amount</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.slice(0, 50).map((r) => (
          <TableRow key={r.id}>
            <TableCell className="text-muted-foreground">
              {formatDate(r.effective_date)}
            </TableCell>
            <TableCell>
              <Link
                href={`/employees/${r.employee_id}`}
                className="font-medium hover:text-primary hover:underline"
              >
                {r.first_name} {r.last_name}
              </Link>
              <div className="text-xs text-muted-foreground">
                {r.department} · {r.level}
              </div>
            </TableCell>
            <TableCell>
              <CountryFlag country={r.country} />
            </TableCell>
            <TableCell>
              <Badge variant={REASON_VARIANT[r.reason] ?? "outline"}>
                {r.reason}
              </Badge>
            </TableCell>
            <TableCell className="text-right tabular-nums">
              <div>{formatCurrency(Number(r.amount), r.currency_code)}</div>
              {r.currency_code !== "USD" && (
                <div className="text-xs text-muted-foreground">
                  ≈ {formatCurrency(Number(r.amount_usd))}
                </div>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
