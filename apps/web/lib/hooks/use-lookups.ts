"use client";

import { useQuery } from "@tanstack/react-query";

import { lookupsApi } from "@/lib/api/lookups";

/** Departments, levels, and currencies in one fetch. Cached aggressively
 *  — this data effectively never changes during a session. */
export function useLookups() {
  return useQuery({
    queryKey: ["lookups"],
    queryFn: lookupsApi.get,
    staleTime: 60 * 60 * 1000, // 1h
    gcTime: 24 * 60 * 60 * 1000,
  });
}
