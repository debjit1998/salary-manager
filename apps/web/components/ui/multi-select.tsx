"use client";

import { Check, ChevronDown } from "lucide-react";
import { useMemo, useState } from "react";

import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export interface MultiSelectOption {
  value: string | number;
  label: string;
}

interface Props {
  options: MultiSelectOption[];
  value: (string | number)[];
  onChange: (next: (string | number)[]) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}

/** A multi-select dropdown that looks like a styled <select> but
 *  supports multiple values. Trigger shows:
 *    - the placeholder when nothing is selected
 *    - the single label when exactly one is selected
 *    - "N selected" when more than one is selected
 *
 *  The popover keeps the trigger's width via
 *  `var(--radix-popover-trigger-width)` so it never feels misaligned. */
export function MultiSelect({
  options,
  value,
  onChange,
  placeholder = "Select…",
  disabled,
  className,
}: Props) {
  const [open, setOpen] = useState(false);

  const summary = useMemo(() => {
    if (value.length === 0) return placeholder;
    if (value.length === 1) {
      return (
        options.find((o) => o.value === value[0])?.label ?? `${value[0]}`
      );
    }
    return `${value.length} selected`;
  }, [value, options, placeholder]);

  function toggle(v: string | number) {
    onChange(
      value.includes(v) ? value.filter((x) => x !== v) : [...value, v],
    );
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          disabled={disabled}
          aria-haspopup="listbox"
          aria-expanded={open}
          className={cn(
            "flex h-9 w-full items-center justify-between gap-2 rounded-md border border-input bg-background px-3 py-1 text-sm ring-offset-background transition-colors",
            "hover:bg-slate-50",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
            "disabled:cursor-not-allowed disabled:opacity-50",
            value.length === 0 && "text-muted-foreground",
            className,
          )}
        >
          <span className="truncate">{summary}</span>
          <ChevronDown
            className={cn(
              "size-4 shrink-0 opacity-50 transition-transform",
              open && "rotate-180",
            )}
          />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        sideOffset={4}
        className="w-[var(--radix-popover-trigger-width)] p-1"
      >
        {options.length === 0 ? (
          <p className="px-2 py-1.5 text-xs text-muted-foreground">Loading…</p>
        ) : (
          <div className="max-h-60 overflow-y-auto">
            {options.map((opt) => {
              const checked = value.includes(opt.value);
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => toggle(opt.value)}
                  className={cn(
                    "flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm transition-colors hover:bg-slate-50",
                    checked && "text-foreground",
                  )}
                >
                  <Check
                    className={cn(
                      "size-4 shrink-0 transition-opacity",
                      checked
                        ? "text-primary opacity-100"
                        : "text-slate-300 opacity-0",
                    )}
                  />
                  <span className="truncate">{opt.label}</span>
                </button>
              );
            })}
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
