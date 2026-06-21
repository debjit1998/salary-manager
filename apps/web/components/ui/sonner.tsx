"use client";

import { Toaster as SonnerToaster } from "sonner";

/** Sonner is the toast lib shipped with shadcn. Mount once in the
 *  root layout; call `toast.error("...")` / `toast.success(...)` from
 *  anywhere. */
export function Toaster() {
  return (
    <SonnerToaster
      position="top-right"
      richColors
      closeButton
      toastOptions={{
        classNames: {
          toast: "group toast group-[.toaster]:bg-background group-[.toaster]:text-foreground group-[.toaster]:border-border group-[.toaster]:shadow-lg",
        },
      }}
    />
  );
}
