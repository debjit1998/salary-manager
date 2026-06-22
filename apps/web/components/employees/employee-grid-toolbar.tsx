"use client";

import {
  ChevronLeft,
  ChevronRight,
  Download,
  ListFilter,
  Loader2,
  Search,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { AxiosError } from "axios";
import { toast } from "sonner";

import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { downloadBlob, employeesApi } from "@/lib/api/employees";
import { cn } from "@/lib/utils";

import { ColumnFilter } from "./column-filter";
import { useEmployeesCtx } from "./employees-context";

interface Props {
  total: number;
  isFetching: boolean;
}

/** Top bar above the grid. Layout:
 *
 *     [⌕filter] [🔍 search...]                10,000 results  ‹ 1 / 200 ›
 *
 *  - left:  filter icon (popover for employment_type), search input
 *  - right: result count + pagination
 */
export function EmployeeGridToolbar({ total, isFetching }: Props) {
  const { state, update } = useEmployeesCtx();

  // Debounce search 300ms
  const [local, setLocal] = useState(state.q ?? "");
  useEffect(() => {
    setLocal(state.q ?? "");
  }, [state.q]);
  useEffect(() => {
    const next = local.trim() || undefined;
    if (next === state.q) return;
    const t = setTimeout(() => update({ q: next, page: 1 }), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [local]);

  const totalPages = Math.max(1, Math.ceil(total / state.size));
  const hasGlobalFilters = (state.employment_type?.length ?? 0) > 0;

  const [downloading, setDownloading] = useState(false);
  async function onDownload() {
    if (downloading) return;
    setDownloading(true);
    try {
      // Strip page/size — the export ignores them and returns every match.
      const { page: _p, size: _s, ...exportParams } = state;
      const blob = await employeesApi.exportCsv(exportParams);
      const today = new Date().toISOString().slice(0, 10);
      downloadBlob(blob, `employees-${today}.csv`);
    } catch (error) {
      const ax = error as AxiosError<{ detail?: string }>;
      toast.error(ax.response?.data?.detail ?? "Couldn't download the CSV.");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="my-4 flex items-center justify-between gap-3">
      <div className="flex flex-1 items-center gap-2">
        <Popover>
          <PopoverTrigger asChild>
            <button
              type="button"
              className={cn(
                "flex size-9 items-center justify-center rounded-md border border-transparent text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900",
                hasGlobalFilters && "border-primary/30 bg-primary/10 text-primary",
              )}
              aria-label="Filter"
            >
              <ListFilter className="size-4" />
            </button>
          </PopoverTrigger>
          <PopoverContent align="start" className="w-56 p-0">
            <ColumnFilter filterKey="employment_type" title="Employment type" />
          </PopoverContent>
        </Popover>

        <div className="relative max-w-md flex-1">
          <Search
            className={cn(
              "pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400",
              local && "text-primary",
            )}
          />
          <input
            value={local}
            onChange={(e) => setLocal(e.target.value)}
            placeholder="Search by name or email"
            className="h-9 w-full rounded-md border border-transparent bg-transparent pl-9 pr-8 text-sm placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
          />
          {local && (
            <button
              type="button"
              onClick={() => setLocal("")}
              className="absolute right-2 top-1/2 flex size-5 -translate-y-1/2 items-center justify-center rounded text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              aria-label="Clear search"
            >
              <X className="size-3" />
            </button>
          )}
        </div>
      </div>

      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={onDownload}
          disabled={downloading || total === 0}
          className={cn(
            "flex h-8 items-center gap-1.5 rounded-md border border-slate-200 px-2.5 text-xs font-medium text-slate-700 transition-colors",
            "hover:bg-slate-50 hover:text-slate-900",
            "disabled:cursor-not-allowed disabled:opacity-50",
          )}
          aria-label="Download CSV of filtered employees"
          title="Download CSV of every row matching the current filters & sort"
        >
          {downloading ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <Download className="size-3.5" />
          )}
          {downloading ? "Preparing…" : "CSV"}
        </button>

        <span
          className={cn(
            "text-sm tabular-nums text-slate-700 transition-opacity",
            isFetching && "opacity-50",
          )}
        >
          <span className="font-medium">{total.toLocaleString()}</span> results
        </span>

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => update({ page: state.page - 1 })}
            disabled={state.page <= 1}
            className="flex size-7 items-center justify-center rounded text-slate-600 transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-transparent"
            aria-label="Previous page"
          >
            <ChevronLeft className="size-4" />
          </button>
          <span className="px-1 text-sm tabular-nums text-slate-600">
            {state.page} / {totalPages.toLocaleString()}
          </span>
          <button
            type="button"
            onClick={() => update({ page: state.page + 1 })}
            disabled={state.page >= totalPages}
            className="flex size-7 items-center justify-center rounded text-slate-600 transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-transparent"
            aria-label="Next page"
          >
            <ChevronRight className="size-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
