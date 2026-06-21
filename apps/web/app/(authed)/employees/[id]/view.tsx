"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  ArrowLeft,
  ArrowUpRight,
  Briefcase,
  Building2,
  CalendarDays,
  Coins,
  Globe2,
  Pencil,
  Plus,
  TrendingUp,
  Users,
} from "lucide-react";

import { AddEquityGrantSheet } from "@/components/employees/add-equity-grant-sheet";
import { AddSalaryChangeSheet } from "@/components/employees/add-salary-change-sheet";
import { BandBadge } from "@/components/employees/band-badge";
import { CountryFlag } from "@/components/employees/country-flag";
import { EditEmployeeSheet } from "@/components/employees/edit-employee-sheet";
import { SalaryTimelineChart } from "@/components/employees/salary-timeline-chart";
import { EMPLOYEES_RETURN_KEY } from "@/components/employees/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatCurrency, formatDate } from "@/lib/format";
import { useDocumentTitle } from "@/lib/hooks/use-document-title";
import { useEmployee } from "@/lib/hooks/use-employees";

const REASON_VARIANT: Record<
  string,
  "default" | "secondary" | "success" | "warning"
> = {
  hire: "secondary",
  raise: "success",
  promo: "default",
  adjustment: "warning",
};

const EMPLOYMENT_LABELS: Record<string, string> = {
  full_time: "Full-time",
  part_time: "Part-time",
  contractor: "Contractor",
};

export function EmployeeDetailView() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const { data: employee, isLoading, isError } = useEmployee(id);

  // Once the employee loads, set the browser tab to their name.
  // The server metadata gives us a sensible fallback ("Employee · Salary
  // Manager") while loading or on error.
  useDocumentTitle(
    employee ? `${employee.first_name} ${employee.last_name}` : undefined,
  );

  const [editOpen, setEditOpen] = useState(false);
  const [salaryOpen, setSalaryOpen] = useState(false);
  const [grantOpen, setGrantOpen] = useState(false);

  // Read once on mount: when the user came from /employees, restore the
  // filters / sort / page they had. Falls back to plain /employees if
  // there's nothing saved (e.g. shared deep-link to a detail page).
  const [backHref, setBackHref] = useState("/employees");
  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved = sessionStorage.getItem(EMPLOYEES_RETURN_KEY);
    if (saved) setBackHref(`/employees${saved}`);
  }, []);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-7xl space-y-6 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (isError || !employee) {
    return (
      <div className="mx-auto max-w-7xl p-8">
        <Link
          href={backHref}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> Back to employees
        </Link>
        <div className="mt-8 rounded-lg border border-destructive/30 bg-destructive/5 p-8 text-center text-sm">
          <p className="font-medium text-destructive">
            Couldn't load employee.
          </p>
        </div>
      </div>
    );
  }

  const isActive = employee.status === "active";

  return (
    <>
      <div className="mx-auto max-w-7xl space-y-6 p-8">
        {/* Top bar */}
        <Link
          href={backHref}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> Back to employees
        </Link>

        {/* Header */}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-semibold tracking-tight">
                {employee.first_name} {employee.last_name}
              </h1>
              <Badge variant={isActive ? "success" : "secondary"}>
                {isActive ? "Active" : "Terminated"}
              </Badge>
            </div>
            <p className="font-mono text-sm text-muted-foreground">
              {employee.employee_no} · {employee.email}
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => setEditOpen(true)}>
              <Pencil className="size-4" /> Edit profile
            </Button>
            <Button variant="outline" onClick={() => setGrantOpen(true)}>
              <Plus className="size-4" /> Add grant
            </Button>
            <Button onClick={() => setSalaryOpen(true)}>
              <TrendingUp className="size-4" /> Record raise
            </Button>
          </div>
        </div>

        {/* Top grid: Profile / Current comp / Equity */}
        <div className="grid gap-4 lg:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Profile</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <DetailRow
                icon={<Building2 className="size-4 text-muted-foreground" />}
                label="Department"
                value={employee.department}
              />
              <DetailRow
                icon={<Briefcase className="size-4 text-muted-foreground" />}
                label="Level"
                value={
                  <span className="font-mono text-xs">{employee.level}</span>
                }
              />
              <DetailRow
                icon={<Globe2 className="size-4 text-muted-foreground" />}
                label="Country"
                value={<CountryFlag country={employee.country} />}
              />
              <DetailRow
                icon={<Briefcase className="size-4 text-muted-foreground" />}
                label="Employment"
                value={EMPLOYMENT_LABELS[employee.employment_type]}
              />
              <DetailRow
                icon={<CalendarDays className="size-4 text-muted-foreground" />}
                label="Hired"
                value={formatDate(employee.hire_date)}
              />
              <DetailRow
                icon={<Users className="size-4 text-muted-foreground" />}
                label="Manager"
                value={
                  employee.manager ? (
                    <Link
                      href={`/employees/${employee.manager.id}`}
                      className="inline-flex items-center gap-0.5 text-primary hover:underline"
                    >
                      {employee.manager.first_name} {employee.manager.last_name}
                      <ArrowUpRight className="size-3" />
                    </Link>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )
                }
              />
              <DetailRow
                icon={<Users className="size-4 text-muted-foreground" />}
                label="Direct reports"
                value={employee.direct_reports_count.toLocaleString()}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Current compensation</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {employee.current_salary ? (
                <>
                  <div>
                    <div className="text-3xl font-semibold tabular-nums">
                      {formatCurrency(
                        Number(employee.current_salary.amount),
                        employee.current_salary.currency_code,
                      )}
                    </div>
                    {employee.current_salary.currency_code !== "USD" && (
                      <div className="text-sm text-muted-foreground">
                        ≈{" "}
                        {formatCurrency(
                          Number(employee.current_salary.amount_usd),
                          "USD",
                        )}{" "}
                        USD
                      </div>
                    )}
                    <div className="mt-1 text-xs text-muted-foreground">
                      Annual base · effective{" "}
                      {formatDate(employee.current_salary.effective_date)}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">Band:</span>
                    <BandBadge position={employee.band_position} />
                  </div>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No salary history yet.
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Coins className="size-4 text-muted-foreground" />
                Equity
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <div className="text-3xl font-semibold tabular-nums">
                  {employee.total_shares.toLocaleString()}
                </div>
                <div className="text-sm text-muted-foreground">
                  shares · {employee.equity_grants.length}{" "}
                  {employee.equity_grants.length === 1 ? "grant" : "grants"}
                </div>
              </div>
              {employee.equity_grants.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No equity grants yet.
                </p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Salary timeline chart */}
        {employee.salary_changes.length > 1 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Salary timeline (USD)</CardTitle>
            </CardHeader>
            <CardContent>
              <SalaryTimelineChart history={employee.salary_changes} />
            </CardContent>
          </Card>
        )}

        {/* Salary history table */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Salary history</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Effective</TableHead>
                  <TableHead>Reason</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                  <TableHead className="text-right">USD</TableHead>
                  <TableHead>Note</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {employee.salary_changes.length === 0 ? (
                  <TableRow className="hover:bg-transparent">
                    <TableCell
                      colSpan={5}
                      className="py-8 text-center text-sm text-muted-foreground"
                    >
                      No salary history.
                    </TableCell>
                  </TableRow>
                ) : (
                  employee.salary_changes.map((c) => (
                    <TableRow key={c.id}>
                      <TableCell>{formatDate(c.effective_date)}</TableCell>
                      <TableCell>
                        <Badge variant={REASON_VARIANT[c.reason] ?? "outline"}>
                          {c.reason}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatCurrency(
                          Number(c.amount),
                          c.currency_code,
                        )}
                      </TableCell>
                      <TableCell className="text-right tabular-nums text-muted-foreground">
                        {formatCurrency(Number(c.amount_usd))}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {c.note ?? "—"}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Equity grants table */}
        {employee.equity_grants.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Equity grants</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead>Grant date</TableHead>
                    <TableHead className="text-right">Shares</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {employee.equity_grants.map((g) => (
                    <TableRow key={g.id}>
                      <TableCell>{formatDate(g.grant_date)}</TableCell>
                      <TableCell className="text-right tabular-nums">
                        {g.shares.toLocaleString()}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </div>

      <EditEmployeeSheet
        employee={employee}
        open={editOpen}
        onOpenChange={setEditOpen}
      />
      <AddSalaryChangeSheet
        employee={employee}
        open={salaryOpen}
        onOpenChange={setSalaryOpen}
      />
      <AddEquityGrantSheet
        employee={employee}
        open={grantOpen}
        onOpenChange={setGrantOpen}
      />
    </>
  );
}

function DetailRow({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="flex items-center gap-2 text-muted-foreground">
        {icon}
        {label}
      </span>
      <span className="text-right">{value}</span>
    </div>
  );
}
