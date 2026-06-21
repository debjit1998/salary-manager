"use client";

import { createContext, useContext } from "react";

import type { LookupsResponse } from "@/types/api";

import type { EmployeeQueryState } from "./types";

export interface EmployeesContextValue {
  state: EmployeeQueryState;
  update: (patch: Partial<EmployeeQueryState>) => void;
  lookups: LookupsResponse | undefined;
}

const Ctx = createContext<EmployeesContextValue | null>(null);

export const EmployeesProvider = Ctx.Provider;

export function useEmployeesCtx(): EmployeesContextValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useEmployeesCtx must be used inside EmployeesProvider");
  return v;
}
