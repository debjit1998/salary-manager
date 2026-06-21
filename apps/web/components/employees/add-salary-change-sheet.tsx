"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
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
import type { EmployeeDetail } from "@/types/api";

const schema = z.object({
  effective_date: z.string().min(1),
  amount: z
    .string()
    .min(1)
    .refine((v) => Number(v) > 0, "must be positive"),
  currency_code: z.enum(["USD", "GBP", "INR"]),
  reason: z.enum(["raise", "promo", "adjustment", "hire"]),
  note: z.string().optional(),
});
type FormValues = z.infer<typeof schema>;

interface Props {
  employee: EmployeeDetail;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}

const today = () => new Date().toISOString().slice(0, 10);

export function AddSalaryChangeSheet({ employee, open, onOpenChange }: Props) {
  const { mutate, isPending } = useAddSalaryChange(employee.id);

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
    },
  });

  function onSubmit(values: FormValues) {
    mutate(
      { ...values, note: values.note || null },
      {
        onSuccess: () => {
          toast.success("Salary change recorded");
          onOpenChange(false);
          form.reset();
        },
        onError: () => toast.error("Failed to record salary change"),
      },
    );
  }

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
                      <SelectItem value="promo">Promotion</SelectItem>
                      <SelectItem value="adjustment">Adjustment</SelectItem>
                      <SelectItem value="hire">Hire</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

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
                {isPending ? "Saving…" : "Record change"}
              </Button>
            </SheetFooter>
          </form>
        </Form>
      </SheetContent>
    </Sheet>
  );
}
