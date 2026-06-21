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
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { useAddEquityGrant } from "@/lib/hooks/use-employees";
import type { EmployeeDetail } from "@/types/api";

const schema = z.object({
  grant_date: z.string().min(1),
  shares: z.coerce.number().int().positive(),
});
type FormValues = z.infer<typeof schema>;

interface Props {
  employee: EmployeeDetail;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}

const today = () => new Date().toISOString().slice(0, 10);

export function AddEquityGrantSheet({ employee, open, onOpenChange }: Props) {
  const { mutate, isPending } = useAddEquityGrant(employee.id);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { grant_date: today(), shares: 0 },
  });

  function onSubmit(values: FormValues) {
    mutate(values, {
      onSuccess: () => {
        toast.success("Equity grant recorded");
        onOpenChange(false);
        form.reset({ grant_date: today(), shares: 0 });
      },
      onError: () => toast.error("Failed to record grant"),
    });
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>Record an equity grant</SheetTitle>
          <SheetDescription>
            Adds a new equity grant for {employee.first_name} {employee.last_name}.
            Multiple grants accumulate into the total share count.
          </SheetDescription>
        </SheetHeader>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="mt-6 space-y-4"
          >
            <FormField
              control={form.control}
              name="grant_date"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Grant date</FormLabel>
                  <FormControl>
                    <Input type="date" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="shares"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Number of shares</FormLabel>
                  <FormControl>
                    <Input type="number" min={1} step={1} {...field} />
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
                {isPending ? "Saving…" : "Record grant"}
              </Button>
            </SheetFooter>
          </form>
        </Form>
      </SheetContent>
    </Sheet>
  );
}
