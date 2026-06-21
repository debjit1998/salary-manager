"use client";

import { useEffect } from "react";

const APP_NAME = "Salary Manager";

/** Sets the document title for a client-component page.
 *
 *  Next.js App Router can't read a `metadata` export from a
 *  client-component file, so the root layout owns the template
 *  ("%s · Salary Manager") and each page nudges the title from
 *  the client via this hook.
 *
 *  Pass `undefined` to fall back to just the app name. */
export function useDocumentTitle(title: string | undefined): void {
  useEffect(() => {
    if (typeof document === "undefined") return;
    document.title = title ? `${title} · ${APP_NAME}` : APP_NAME;
  }, [title]);
}
