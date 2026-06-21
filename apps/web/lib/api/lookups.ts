import { api } from "./client";
import type { LookupsResponse } from "@/types/api";

export const lookupsApi = {
  get: () => api.get<LookupsResponse>("/lookups").then((r) => r.data),
};
