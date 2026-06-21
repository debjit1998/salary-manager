import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merges Tailwind class strings, deduping conflicting utilities. The
 *  canonical shadcn helper — used by every UI component. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
