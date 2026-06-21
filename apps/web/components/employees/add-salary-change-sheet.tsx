"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { useAddSalaryChange } from "@/lib/hooks/use-employees";
import { useLookups } from "@/lib/hooks/use-lookups";
import type { EmployeeDetail } from "@/types/api";

const schema = z
  .object({
    effective_date: z.string().min(1),
    amount: z
      .string()
      .min(1)
      .refine((v) => Number(v) > 0, "must be positive"),
    currency_code: z.enum(["USD", "GBP", "INR"]),
    reason: z.enum(["raise", "promo", "adjustment", "hire"]),
    note: z.string().optional(),
    // Optional in general; required when reason === 'promo' (refine below).
    new_level_id: z.coerce.number().int().optional(),
  })
  .refine(
    (data) => data.reason !== "promo" || data.new_level_id !== undefined,
    {
      message: "Level is required for a promotion",
      path: ["new_level_id"],
    },
  );
type FormValues = z.infer<typeof schema>;

interface Props {
  employee: EmployeeDetail;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}

const today = () => new Date().toISOString().slice(0, 10);

export function AddSalaryChangeSheet({ employee, open, onOpenChange }: Props) {
  const { mutate, isPending } = useAddSalaryChange(employee.id);
  const { data: lookups } = useLookups();

  // Levels sorted by rank, plus the employee's current rank and the
  // levels above it. If there are no levels above, hide the Promo
  // option entirely — you can't promote an L7.
  const sortedLevels = useMemo(
    () => [...(lookups?.levels ?? [])].sort((a, b) => a.rank - b.rank),
    [lookups],
  );
  const currentRank = useMemo(
    () =>
      sortedLevels.find((l) => l.id === employee.level_id)?.rank,
    [sortedLevels, employee.level_id],
  );
  const promotableLevels = useMemo(
    () =>
      currentRank === undefined
        ? []
        : sortedLevels.filter((l) => l.rank > currentRank),
    [sortedLevels, currentRank],
  );
  const canPromo = promotableLevels.length > 0;

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      effective_date: today(),
      amount: "",
      currency_code: (employee.current_salary?.currency_code ?? "USD") as
        | "USD"
        | "GBP"
        | "INR",
      reason: "raise",
      note: "",
      new_level_id: undefined,
    },
  });

  const reason = form.watch("reason");
  const isPromo = reason === "promo";

  // When the user picks "promo", default the new level to the next
  // rank up. They can change it to a skip-level promotion if they
  // want. When they switch away from promo, clear it.
  useEffect(() => {
    if (isPromo) {
      const current = form.getValues("new_level_id");
      if (current === undefined && promotableLevels.length > 0) {
        form.setValue("new_level_id", promotableLevels[0].id, {
          shouldValidate: true,
        });
      }
    } else {
      form.setValue("new_level_id", undefined);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPromo, promotableLevels]);

  function onSubmit(values: FormValues) {
    mutate(
      {
        ...values,
        note: values.note || null,
        new_level_id: isPromo ? values.new_level_id : null,
      },
      {
        onSuccess: () => {
          toast.success(
            isPromo ? "Promotion recorded" : "Salary change recorded",
          );
          onOpenChange(false);
          form.reset();
        },
        onError: () => toast.error("Failed to record salary change"),
      },
    );
  }

  const currentLevelCode = sortedLevels.find(
    (l) => l.id === employee.level_id,
  )?.code;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>Record a salary change</SheetTitle>
          <SheetDescription>
            Appends a new row to {employee.first_name}'s salary history.
            This becomes the current salary as of the effective date.
          </SheetDescription>
        </SheetHeader>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="mt-6 space-y-4"
          >
            <FormField
              control={form.control}
              name="effective_date"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Effective date</FormLabel>
                  <FormControl>
                    <Input type="date" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid grid-cols-3 gap-3">
              <FormField
                control={form.control}
                name="amount"
                render={({ field }) => (
                  <FormItem className="col-span-2">
                    <FormLabel>Annual amount</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        step="0.01"
                        placeholder="e.g. 165000"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="currency_code"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Currency</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="USD">USD</SelectItem>
                        <SelectItem value="GBP">GBP</SelectItem>
                        <SelectItem value="INR">INR</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="reason"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Reason</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="raise">Raise</SelectItem>
                      {canPromo && (
                        <SelectItem value="promo">Promotion</SelectItem>
                      )}
                      <SelectItem value="adjustment">Adjustment</SelectItem>
                      <SelectItem value="hire">Hire</SelectItem>
                    </SelectContent>
                  </Select>
                  {!canPromo && (
                    <FormDescription>
                      Promotion is hidden — {employee.first_name} is at the
                      top level ({currentLevelCode}).
                    </FormDescription>
                  )}
                  <FormMessage />
                </FormItem>
              )}
            />

            {isPromo && (
              <FormField
                control={form.control}
                name="new_level_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>New level</FormLabel>
                    <Select
                      value={field.value ? String(field.value) : ""}
                      onValueChange={(v) => field.onChange(Number(v))}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select the new level" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {promotableLevels.map((l) => (
                          <SelectItem key={l.id} value={String(l.id)}>
                            {l.code}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormDescription>
                      Currently {currentLevelCode}. The employee's level
                      will be updated when the promotion is saved.
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}

            <FormField
              control={form.control}
              name="note"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Note (optional)</FormLabel>
                  <FormControl>
                    <Textarea placeholder="e.g. annual review" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <SheetFooter className="mt-8">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isPending}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isPending}>
                {isPending
                  ? "Saving…"
                  : isPromo
                    ? "Record promotion"
                    : "Record change"}
              </Button>
            </SheetFooter>
          </form>
        </Form>
      </SheetContent>
    </Sheet>
  );
}
