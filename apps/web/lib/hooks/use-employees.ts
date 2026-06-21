"use client";

import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  employeesApi,
  type ListEmployeesParams,
} from "@/lib/api/employees";
import type {
  EmployeeDetail,
  EmployeeUpdate,
  EquityGrantCreate,
  SalaryChangeCreate,
} from "@/types/api";

const KEY = {
  list: (params: ListEmployeesParams) => ["employees", "list", params] as const,
  detail: (id: string) => ["employees", "detail", id] as const,
};

/** Server-paginated employees list. `keepPreviousData` keeps the
 *  previous page visible while the next one loads — avoids the table
 *  flashing empty on every page/filter change. */
export function useEmployees(params: ListEmployeesParams) {
  return useQuery({
    queryKey: KEY.list(params),
    queryFn: () => employeesApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useEmployee(id: string) {
  return useQuery({
    queryKey: KEY.detail(id),
    queryFn: () => employeesApi.get(id),
    enabled: Boolean(id),
  });
}

export function useUpdateEmployee(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: EmployeeUpdate) => employeesApi.update(id, body),
    onSuccess: (data: EmployeeDetail) => {
      qc.setQueryData(KEY.detail(id), data);
      qc.invalidateQueries({ queryKey: ["employees", "list"] });
    },
  });
}

export function useAddSalaryChange(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SalaryChangeCreate) =>
      employeesApi.addSalaryChange(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY.detail(id) });
      qc.invalidateQueries({ queryKey: ["employees", "list"] });
    },
  });
}

export function useAddEquityGrant(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: EquityGrantCreate) =>
      employeesApi.addEquityGrant(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY.detail(id) });
    },
  });
}
