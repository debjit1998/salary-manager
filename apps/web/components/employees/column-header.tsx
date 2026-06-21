"use client";

import { ArrowDown, ArrowUp, ChevronsUpDown, ListFilter } from "lucide-react";

import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

import { ColumnFilter } from "./column-filter";
import { useEmployeesCtx } from "./employees-context";
import type { FilterKey } from "./types";

interface Props {
  displayName: string;
  /** Maps to the API's `sort` query key (e.g. "hire_date"). If unset,
   *  the column header is not sortable. */
  sortKey?: string;
  /** Maps to a URL filter key (e.g. "country"). If unset, no filter
   *  popover is rendered. */
  filterKey?: FilterKey;
}

/** Custom AgGrid header that renders our own sort + filter UI.
 *
 *  AgGrid's built-in sort/filter is disabled (sortable: false on every
 *  column, no filter prop) because we want everything to be
 *  server-driven. Clicking the column name toggles sort via our
 *  callback; clicking the filter icon opens a popover that updates the
 *  URL filter state. */
export function EmployeeColumnHeader(props: Props) {
  const { state, update } = useEmployeesCtx();

  const sorted = props.sortKey
    ? state.sort === props.sortKey
      ? "asc"
      : state.sort === `-${props.sortKey}`
        ? "desc"
        : null
    : null;

  function toggleSort() {
    if (!props.sortKey) return;
    const next =
      sorted === null ? props.sortKey : sorted === "asc" ? `-${props.sortKey}` : undefined;
    update({ sort: next, page: 1 });
  }

  const filterCount = props.filterKey
    ? (state[props.filterKey]?.length ?? 0)
    : 0;
  const filterActive = filterCount > 0;

  return (
    <div className="flex h-full w-full items-center justify-between gap-1">
      <button
        type="button"
        onClick={toggleSort}
        disabled={!props.sortKey}
        className={cn(
          "flex items-center gap-1 truncate text-sm font-medium text-slate-700",
          props.sortKey &&
            "transition-colors hover:text-slate-900 disabled:hover:text-slate-700",
        )}
      >
        {props.displayName}
        {props.sortKey ? (
          sorted === "asc" ? (
            <ArrowUp className="size-3 text-slate-700" />
          ) : sorted === "desc" ? (
            <ArrowDown className="size-3 text-slate-700" />
          ) : (
            <ChevronsUpDown className="size-3 text-slate-400" />
          )
        ) : null}
      </button>

      {props.filterKey ? (
        <Popover>
          <PopoverTrigger asChild>
            <button
              type="button"
              className={cn(
                "flex h-6 items-center justify-center gap-1 rounded px-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700",
                filterActive && "bg-primary/10 text-primary hover:bg-primary/15",
              )}
              aria-label={`Filter ${props.displayName}`}
            >
              <ListFilter className="size-3.5" />
              {filterCount > 0 && (
                <span className="text-[11px] font-medium tabular-nums">
                  {filterCount}
                </span>
              )}
            </button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-56 p-0">
            <ColumnFilter filterKey={props.filterKey} title={props.displayName} />
          </PopoverContent>
        </Popover>
      ) : null}
    </div>
  );
}
