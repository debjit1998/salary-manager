import type { BandPosition } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const VARIANTS: Record<
  BandPosition,
  { variant: "success" | "warning" | "danger"; dot: string; label: string }
> = {
  within: { variant: "success", dot: "bg-emerald-500", label: "Within" },
  below: { variant: "danger", dot: "bg-red-500", label: "Below" },
  above: { variant: "warning", dot: "bg-amber-500", label: "Above" },
};

export function BandBadge({ position }: { position: BandPosition | null }) {
  if (!position) {
    return <span className="text-xs text-muted-foreground">—</span>;
  }
  const v = VARIANTS[position];
  return (
    <Badge variant={v.variant} className="gap-1.5">
      <span className={cn("size-1.5 rounded-full", v.dot)} />
      {v.label}
    </Badge>
  );
}
