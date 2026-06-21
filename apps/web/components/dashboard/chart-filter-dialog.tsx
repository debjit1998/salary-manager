"use client";

import { ListFilter, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  MultiSelect,
  type MultiSelectOption,
} from "@/components/ui/multi-select";
import { useLookups } from "@/lib/hooks/use-lookups";
import { cn } from "@/lib/utils";
import type { EmployeeFilters } from "@/types/api";

/** Identifies a single filter dimension. Matches the keys of
 *  EmployeeFilters that the dashboard exposes — `status` and any
 *  not-yet-supported fields are intentionally omitted. */
export type ChartFilterKey =
  | "country"
  | "department_id"
  | "level_id"
  | "employment_type"
  | "salary_band"
  | "band_position";

interface Props {
  /** Which filters this particular chart supports. Hide the ones that
   *  would be redundant (e.g. don't show "country" on the "headcount
   *  by country" chart — it's the dimension). */
  availableFilters: ChartFilterKey[];
  value: EmployeeFilters;
  onChange: (next: EmployeeFilters) => void;
}

type Option = MultiSelectOption;

const COUNTRY_OPTIONS: Option[] = [
  { value: "US", label: "🇺🇸 United States" },
  { value: "UK", label: "🇬🇧 United Kingdom" },
  { value: "IN", label: "🇮🇳 India" },
];

const EMPLOYMENT_OPTIONS: Option[] = [
  { value: "full_time", label: "Full-time" },
  { value: "part_time", label: "Part-time" },
  { value: "contractor", label: "Contractor" },
];

const BAND_OPTIONS: Option[] = [
  { value: "below", label: "Below band" },
  { value: "within", label: "Within band" },
  { value: "above", label: "Above band" },
];

const SALARY_BAND_OPTIONS: Option[] = [
  { value: "0-10000", label: "< $10k" },
  { value: "10000-50000", label: "$10k – $50k" },
  { value: "50000-100000", label: "$50k – $100k" },
  { value: "100000-150000", label: "$100k – $150k" },
  { value: "150000-200000", label: "$150k – $200k" },
  { value: "200000-300000", label: "$200k – $300k" },
  { value: "300000+", label: "$300k+" },
];

const FILTER_TITLE: Record<ChartFilterKey, string> = {
  country: "Country",
  department_id: "Department",
  level_id: "Level",
  employment_type: "Employment type",
  salary_band: "Salary range (USD)",
  band_position: "Comp band position",
};

function activeCount(filters: EmployeeFilters): number {
  return (Object.values(filters) as (unknown[] | undefined)[]).reduce<number>(
    (n, v) => n + (Array.isArray(v) && v.length > 0 ? 1 : 0),
    0,
  );
}

export function ChartFilterDialog({
  availableFilters,
  value,
  onChange,
}: Props) {
  const [open, setOpen] = useState(false);
  const { data: lookups } = useLookups();

  const count = activeCount(value);
  const isActive = count > 0;

  const optionsFor = (key: ChartFilterKey): Option[] => {
    if (key === "country") return COUNTRY_OPTIONS;
    if (key === "employment_type") return EMPLOYMENT_OPTIONS;
    if (key === "band_position") return BAND_OPTIONS;
    if (key === "salary_band") return SALARY_BAND_OPTIONS;
    if (key === "department_id") {
      return (lookups?.departments ?? []).map((d) => ({
        value: d.id,
        label: d.name,
      }));
    }
    if (key === "level_id") {
      return (lookups?.levels ?? []).map((l) => ({
        value: l.id,
        label: l.code,
      }));
    }
    return [];
  };

  function setFor(key: ChartFilterKey, next: (string | number)[]) {
    onChange({
      ...value,
      [key]: next.length ? next : undefined,
    });
  }

  function clearAll() {
    onChange({});
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button
          type="button"
          className={cn(
            "flex h-7 items-center gap-1 rounded-md border border-transparent px-2 text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900",
            isActive &&
              "border-primary/30 bg-primary/10 text-primary hover:bg-primary/15 hover:text-primary",
          )}
          aria-label="Filter chart"
        >
          <ListFilter className="size-3.5" />
          {count > 0 && (
            <span className="text-[11px] font-medium tabular-nums">{count}</span>
          )}
        </button>
      </DialogTrigger>

      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Chart filters</DialogTitle>
          <DialogDescription>
            Narrow this chart to a subset of the org. Filters apply to
            this chart only.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-1 gap-4 py-2 sm:grid-cols-2">
          {availableFilters.map((key) => {
            const options = optionsFor(key);
            const current = ((value as Record<string, unknown>)[key] ?? []) as (
              | string
              | number
            )[];
            return (
              <div key={key} className="space-y-1.5">
                <label className="text-xs font-medium uppercase tracking-wider text-slate-500">
                  {FILTER_TITLE[key]}
                </label>
                <MultiSelect
                  options={options}
                  value={current}
                  onChange={(next) => setFor(key, next)}
                  placeholder={`All ${FILTER_TITLE[key].toLowerCase()}`}
                />
              </div>
            );
          })}
        </div>

        <DialogFooter className="sm:justify-between">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={clearAll}
            disabled={!isActive}
          >
            <X className="size-3.5" />
            Clear all
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={() => setOpen(false)}
          >
            Done
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
