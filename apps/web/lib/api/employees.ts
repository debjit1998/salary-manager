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
  // Filter fields accept arrays. axios is configured (see lib/api/client.ts)
  // to serialise them as repeated query keys (?country=US&country=UK),
  // which is what FastAPI expects for `list[str]` Query params.
  dept_id?: number[];
  country?: string[];
  level_id?: number[];
  employment_type?: string[];
  status?: string[];
  band_position?: string[];
  salary_band?: string[];
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

  // CSV export of every row matching the current filter+sort (no pagination).
  // Returns a Blob so the caller can trigger a browser download via
  // a synthetic anchor. Auth + array-param serialisation come from the
  // shared `api` client.
  exportCsv: (
    params: Omit<ListEmployeesParams, "page" | "size"> = {},
  ): Promise<Blob> =>
    api
      .get<Blob>("/employees/export.csv", { params, responseType: "blob" })
      .then((r) => r.data),
};

/** Trigger a browser download for a blob with the given filename. */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
