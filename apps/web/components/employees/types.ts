import type { BandPosition, Country, EmploymentType } from "@/types/api";

/** Shape of the employees-list URL state. Kept in one place so the
 *  page, filters, table, and URL-sync logic all agree on the keys.
 *
 *  Filter fields are arrays so all column filters can be multi-select.
 *  The UI / URL serialisation treats an empty array the same as
 *  undefined — no filter applied. */
export interface EmployeeQueryState {
  page: number;
  size: number;
  sort?: string;
  q?: string;
  dept_id?: number[];
  country?: Country[];
  level_id?: number[];
  employment_type?: EmploymentType[];
  band_position?: BandPosition[];
  /** Multi-select USD ranges. Values match
   *  ALLOWED_SALARY_BANDS in apps/api/app/src/employee/queries.py. */
  salary_band?: string[];
}

/** The keys of EmployeeQueryState that are multi-select filter arrays.
 *  Centralised so the column-filter / column-header components stay in
 *  sync with the state shape. */
export type FilterKey =
  | "dept_id"
  | "country"
  | "level_id"
  | "employment_type"
  | "band_position"
  | "salary_band";

export const DEFAULT_QUERY: EmployeeQueryState = {
  page: 1,
  size: 50,
};

/** sessionStorage key used to remember the employees list's current
 *  search string. The detail page reads this so its "Back to employees"
 *  link restores filters / sort / page. Lives in `types.ts` (a
 *  non-route module) so both pages can import without entangling
 *  Next.js route discovery. */
export const EMPLOYEES_RETURN_KEY = "salary-manager.employees-search";
