import { api } from "./client";
import type { NLResponse } from "@/types/api";

export const nlApi = {
  query: (question: string) =>
    api
      .post<NLResponse>("/nl-query", { question })
      .then((r) => r.data),
};
