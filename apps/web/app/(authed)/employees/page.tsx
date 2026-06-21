"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo } from "react";

import { EmployeeGrid } from "@/components/employees/employee-grid";
import { EmployeeGridToolbar } from "@/components/employees/employee-grid-toolbar";
import { EmployeesProvider } from "@/components/employees/employees-context";
import {
  DEFAULT_QUERY,
  EMPLOYEES_RETURN_KEY,
  type EmployeeQueryState,
} from "@/components/employees/types";
import { useEmployees } from "@/lib/hooks/use-employees";
import { useLookups } from "@/lib/hooks/use-lookups";
import type { BandPosition, Country, EmploymentType } from "@/types/api";

// ---- URL <-> state helpers ----------------------------------------------
//
// Multi-select filters serialise as repeated keys: ?country=US&country=UK.
// `URLSearchParams.getAll(key)` is the matching read side.

function readNumberList(p: URLSearchParams, key: string): number[] | undefined {
  const xs = p
    .getAll(key)
    .map((s) => Number(s))
    .filter((n) => Number.isFinite(n));
  return xs.length ? xs : undefined;
}

function readStringList<T extends string>(
  p: URLSearchParams,
  key: string,
): T[] | undefined {
  const xs = p.getAll(key) as T[];
  return xs.length ? xs : undefined;
}

function readState(params: URLSearchParams): EmployeeQueryState {
  const num = (k: string) => {
    const v = params.get(k);
    return v ? Number(v) : undefined;
  };
  return {
    page: num("page") ?? DEFAULT_QUERY.page,
    size: num("size") ?? DEFAULT_QUERY.size,
    sort: params.get("sort") ?? undefined,
    q: params.get("q") ?? undefined,
    dept_id: readNumberList(params, "dept_id"),
    country: readStringList<Country>(params, "country"),
    level_id: readNumberList(params, "level_id"),
    employment_type: readStringList<EmploymentType>(params, "employment_type"),
    band_position: readStringList<BandPosition>(params, "band_position"),
  };
}

function writeList(
  p: URLSearchParams,
  key: string,
  values: (string | number)[] | undefined,
): void {
  if (!values?.length) return;
  for (const v of values) p.append(key, String(v));
}

function writeState(state: EmployeeQueryState): URLSearchParams {
  const next = new URLSearchParams();
  if (state.page !== DEFAULT_QUERY.page) next.set("page", String(state.page));
  if (state.size !== DEFAULT_QUERY.size) next.set("size", String(state.size));
  if (state.sort) next.set("sort", state.sort);
  if (state.q) next.set("q", state.q);
  writeList(next, "dept_id", state.dept_id);
  writeList(next, "country", state.country);
  writeList(next, "level_id", state.level_id);
  writeList(next, "employment_type", state.employment_type);
  writeList(next, "band_position", state.band_position);
  return next;
}

function EmployeesView() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const state = useMemo(
    () => readState(new URLSearchParams(searchParams.toString())),
    [searchParams],
  );

  const update = useCallback(
    (patch: Partial<EmployeeQueryState>) => {
      const next: EmployeeQueryState = { ...state, ...patch };
      const qs = writeState(next).toString();
      router.replace(qs ? `/employees?${qs}` : `/employees`, { scroll: false });
    },
    [router, state],
  );

  const { data: lookups } = useLookups();
  const { data, isLoading, isFetching } = useEmployees(state);

  // Remember the current list URL so the detail page can use it as the
  // "Back to employees" target — restoring filters / sort / page.
  useEffect(() => {
    if (typeof window === "undefined") return;
    sessionStorage.setItem(EMPLOYEES_RETURN_KEY, window.location.search);
  }, [searchParams]);

  return (
    <EmployeesProvider value={{ state, update, lookups }}>
      <div className="flex h-full flex-col overflow-hidden p-6 lg:p-8">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Employees
        </h1>
        <EmployeeGridToolbar
          total={data?.total ?? 0}
          isFetching={isFetching}
        />
        <div className="min-h-0 flex-1">
          <EmployeeGrid
            rows={data?.items ?? []}
            isLoading={isLoading || isFetching}
          />
        </div>
      </div>
    </EmployeesProvider>
  );
}

export default function EmployeesPage() {
  return (
    <Suspense fallback={null}>
      <EmployeesView />
    </Suspense>
  );
}
