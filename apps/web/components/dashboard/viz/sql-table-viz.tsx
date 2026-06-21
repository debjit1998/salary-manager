"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface Props {
  sql: string;
  columns: string[];
  rows: Record<string, unknown>[];
}

function formatCell(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export function SqlTableViz({ sql, columns, rows }: Props) {
  return (
    <div className="space-y-3">
      <details className="rounded-md border bg-slate-50 px-3 py-2">
        <summary className="cursor-pointer select-none text-xs font-medium text-slate-600">
          SQL executed
        </summary>
        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all font-mono text-[11px] text-slate-700">
          {sql}
        </pre>
      </details>

      {rows.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          Query returned no rows.
        </p>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                {columns.map((c) => (
                  <TableHead key={c} className="font-mono text-xs">
                    {c}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.slice(0, 100).map((row, i) => (
                <TableRow key={i}>
                  {columns.map((c) => (
                    <TableCell key={c} className="font-mono text-xs">
                      {formatCell(row[c])}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {rows.length > 100 && (
            <div className="border-t px-3 py-2 text-xs text-muted-foreground">
              Showing 100 of {rows.length}.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
