import { api } from "./client";
import type {
  EmployeeDetail,
  EmployeeListResponse,
  EmployeeUpdate,
  EquityGrant,
  EquityGrantCreate,
  SalaryChange,
  SalaryChangeCreate,
} from "@/types/api";

export interface ListEmployeesParams {
  page?: number;
  size?: number;
  sort?: string;
  q?: string;
  dept_id?: number;
  country?: string;
  level_id?: number;
  employment_type?: string;
  status?: string;
}

export const employeesApi = {
  list: (params: ListEmployeesParams = {}) =>
    api
      .get<EmployeeListResponse>("/employees", { params })
      .then((r) => r.data),

  get: (id: string) =>
    api.get<EmployeeDetail>(`/employees/${id}`).then((r) => r.data),

  update: (id: string, body: EmployeeUpdate) =>
    api.patch<EmployeeDetail>(`/employees/${id}`, body).then((r) => r.data),

  addSalaryChange: (id: string, body: SalaryChangeCreate) =>
    api
      .post<SalaryChange>(`/employees/${id}/salary-changes`, body)
      .then((r) => r.data),

  addEquityGrant: (id: string, body: EquityGrantCreate) =>
    api
      .post<EquityGrant>(`/employees/${id}/equity-grants`, body)
      .then((r) => r.data),
};
