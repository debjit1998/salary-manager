"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

interface Props {
  title: string;
  description?: string;
  isLoading?: boolean;
  isError?: boolean;
  /** Right-aligned slot in the card header — typically the
   *  <ChartFilterDialog/> trigger button. */
  filter?: React.ReactNode;
  children: React.ReactNode;
  /** Optional `p-0` etc. on the body if the child needs full bleed. */
  contentClassName?: string;
}

export function ChartCard({
  title,
  description,
  isLoading,
  isError,
  filter,
  children,
  contentClassName,
}: Props) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-2 pb-3">
        <div className="space-y-1">
          <CardTitle className="text-base font-semibold">{title}</CardTitle>
          {description && (
            <CardDescription className="text-xs">{description}</CardDescription>
          )}
        </div>
        {filter}
      </CardHeader>
      <CardContent className={contentClassName ?? "pt-0"}>
        {isError ? (
          <p className="py-6 text-center text-sm text-destructive">
            Failed to load.
          </p>
        ) : isLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : (
          children
        )}
      </CardContent>
    </Card>
  );
}
