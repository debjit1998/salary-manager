"use client";

import { useMutation } from "@tanstack/react-query";

import { nlApi } from "@/lib/api/nl";

/** Fires the NL query and exposes its lifecycle. The result lives on
 *  the mutation object — no cache invalidation needed since each
 *  question is a one-shot ask. */
export function useNLQuery() {
  return useMutation({
    mutationFn: (question: string) => nlApi.query(question),
  });
}
