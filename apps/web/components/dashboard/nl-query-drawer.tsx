"use client";

import { Loader2, Send, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { useNLQuery } from "@/lib/hooks/use-nl";
import { cn } from "@/lib/utils";
import type { NLResponse } from "@/types/api";

import { NLAnswer } from "./nl-answer";

const LAST_KEY = "salary-manager.nl-last";

interface LastNL {
  question: string;
  response: NLResponse;
}

const SUGGESTIONS = [
  "How many employees in each country?",
  "Average salary by level",
  "Top 10 earners overall",
  "Who is below band?",
  "Salary distribution across the org",
];

interface Props {
  /** Custom trigger element. Wrapped in SheetTrigger asChild. */
  children: React.ReactNode;
}

/** Slide-in drawer hosting the NL chat box.
 *
 *  Persistence model:
 *    - On a successful query, save {question, response} to
 *      sessionStorage so the user can close the drawer and not lose
 *      what they just asked.
 *    - On every Sheet open, restore from sessionStorage if present.
 *    - sessionStorage clears on tab close — short-lived by design.
 */
export function NLQueryDrawer({ children }: Props) {
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [lastResponse, setLastResponse] = useState<NLResponse | null>(null);
  const { mutate, isPending, error, reset } = useNLQuery();

  // Restore last Q+A every time the drawer opens (cheap; sessionStorage
  // is in-memory). We don't restore on mount because the drawer is
  // mounted on every dashboard render — would flicker otherwise.
  useEffect(() => {
    if (!open || typeof window === "undefined") return;
    const saved = window.sessionStorage.getItem(LAST_KEY);
    if (!saved) return;
    try {
      const parsed = JSON.parse(saved) as LastNL;
      setQuestion(parsed.question);
      setLastResponse(parsed.response);
    } catch {
      // corrupt; clear
      window.sessionStorage.removeItem(LAST_KEY);
    }
  }, [open]);

  function ask(q: string) {
    const trimmed = q.trim();
    if (!trimmed || isPending) return;
    setQuestion(trimmed);
    reset();
    mutate(trimmed, {
      onSuccess: (response) => {
        setLastResponse(response);
        if (typeof window !== "undefined") {
          window.sessionStorage.setItem(
            LAST_KEY,
            JSON.stringify({ question: trimmed, response }),
          );
        }
      },
    });
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    ask(question);
  }

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>{children}</SheetTrigger>
      <SheetContent
        side="right"
        className="flex w-full flex-col gap-0 p-0 sm:max-w-4xl"
      >
        <SheetHeader className="border-b border-slate-200 px-6 py-5">
          <SheetTitle className="flex items-center gap-2">
            <Sparkles className="size-4 text-primary" />
            Ask the org
          </SheetTitle>
          <SheetDescription>
            Natural-language questions about how the org pays its people.
          </SheetDescription>
        </SheetHeader>

        <div className="border-b border-slate-200 px-6 py-4">
          <form onSubmit={onSubmit} className="flex gap-2">
            <Input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. average salary of L4 engineers in the UK"
              disabled={isPending}
              autoFocus
            />
            <Button type="submit" disabled={isPending || !question.trim()}>
              {isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Send className="size-4" />
              )}
              <span className="hidden sm:inline">Ask</span>
            </Button>
          </form>

          <div className="mt-3 flex flex-wrap gap-1.5">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => ask(s)}
                disabled={isPending}
                className={cn(
                  "rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600 transition-colors",
                  "hover:border-primary/30 hover:bg-primary/5 hover:text-primary",
                  "disabled:cursor-not-allowed disabled:opacity-50",
                )}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {isPending && (
            <div className="flex items-center gap-2 rounded-md border bg-slate-50 px-4 py-3 text-sm text-muted-foreground">
              <Loader2 className="size-3.5 animate-spin" />
              Thinking…
            </div>
          )}

          {error && !isPending && (
            <p className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
              Something went wrong. Try again.
            </p>
          )}

          {lastResponse && !isPending && !error && (
            <div className="rounded-md border bg-card p-4">
              <NLAnswer response={lastResponse} />
            </div>
          )}

          {!lastResponse && !isPending && !error && (
            <p className="text-sm text-slate-500">
              Type a question above or pick a suggestion to get started.
            </p>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
