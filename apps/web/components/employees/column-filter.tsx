"use client";

import { useMemo } from "react";

import { Checkbox } from "@/components/ui/checkbox";

import { useEmployeesCtx } from "./employees-context";
import type { FilterKey } from "./types";

interface Props {
  filterKey: FilterKey;
  title: string;
}

interface Option {
  value: string | number;
  label: string;
}

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

// USD-band buckets — values must match ALLOWED_SALARY_BANDS in the
// backend (apps/api/app/src/employee/queries.py).
const SALARY_BAND_OPTIONS: Option[] = [
  { value: "0-10000", label: "< $10k" },
  { value: "10000-50000", label: "$10k – $50k" },
  { value: "50000-100000", label: "$50k – $100k" },
  { value: "100000-150000", label: "$100k – $150k" },
  { value: "150000-200000", label: "$150k – $200k" },
  { value: "200000-300000", label: "$200k – $300k" },
  { value: "300000+", label: "$300k+" },
];

/** Multi-select filter. Empty selection == no filter. */
export function ColumnFilter({ filterKey, title }: Props) {
  const { state, update, lookups } = useEmployeesCtx();

  const options: Option[] = useMemo(() => {
    if (filterKey === "country") return COUNTRY_OPTIONS;
    if (filterKey === "employment_type") return EMPLOYMENT_OPTIONS;
    if (filterKey === "band_position") return BAND_OPTIONS;
    if (filterKey === "salary_band") return SALARY_BAND_OPTIONS;
    if (filterKey === "dept_id") {
      return (lookups?.departments ?? []).map((d) => ({
        value: d.id,
        label: d.name,
      }));
    }
    if (filterKey === "level_id") {
      return (lookups?.levels ?? []).map((l) => ({
        value: l.id,
        label: l.code,
      }));
    }
    return [];
  }, [filterKey, lookups]);

  // state[filterKey] is always an array | undefined for these keys.
  const current = (state[filterKey] ?? []) as (string | number)[];

  function toggle(value: string | number) {
    const next = current.includes(value)
      ? current.filter((v) => v !== value)
      : [...current, value];
    update({
      [filterKey]: next.length ? next : undefined,
      page: 1,
    } as Partial<typeof state>);
  }

  function clear() {
    update({ [filterKey]: undefined, page: 1 } as Partial<typeof state>);
  }

  return (
    <div>
      <div className="flex items-center justify-between border-b border-slate-100 px-3 py-2">
        <span className="text-xs font-medium uppercase tracking-wider text-slate-500">
          {title}
        </span>
        {current.length > 0 && (
          <button
            type="button"
            onClick={clear}
            className="text-xs text-slate-500 hover:text-slate-900"
          >
            Clear ({current.length})
          </button>
        )}
      </div>
      <div className="max-h-64 overflow-y-auto p-1">
        {options.length === 0 ? (
          <div className="p-3 text-xs text-slate-400">Loading…</div>
        ) : (
          options.map((opt) => {
            const checked = current.includes(opt.value);
            return (
              <label
                key={opt.value}
                className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-slate-50"
              >
                <Checkbox
                  checked={checked}
                  onCheckedChange={() => toggle(opt.value)}
                />
                <span className="truncate">{opt.label}</span>
              </label>
            );
          })
        )}
      </div>
    </div>
  );
}
