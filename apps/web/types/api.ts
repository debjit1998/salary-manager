// TypeScript types mirroring the FastAPI Pydantic schemas.
// Kept in one file so it's easy to spot drift when the backend evolves.

export type Country = "US" | "UK" | "IN";
export type Currency = "USD" | "GBP" | "INR";
export type EmploymentType = "full_time" | "part_time" | "contractor";
export type EmployeeStatus = "active" | "terminated";
export type SalaryReason = "hire" | "raise" | "promo" | "adjustment";
export type BandPosition = "below" | "within" | "above";
export type Dimension = "department" | "level" | "country" | "employment_type";

// --- Lookups -------------------------------------------------------------

export interface Department {
  id: number;
  name: string;
}

export interface Level {
  id: number;
  code: string;
  rank: number;
}

export interface CurrencyRow {
  code: string;
  name: string;
  ratio_to_usd: string;
}

export interface LookupsResponse {
  departments: Department[];
  levels: Level[];
  currencies: CurrencyRow[];
}

// --- Auth ----------------------------------------------------------------

export interface User {
  id: string;
  email: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

// --- Employees -----------------------------------------------------------

export interface CurrentSalary {
  amount: string; // Decimal serialised as string
  currency_code: string;
  amount_usd: string;
  effective_date: string;
}

export interface SalaryChange {
  id: string;
  effective_date: string;
  amount: string;
  currency_code: string;
  amount_usd: string;
  reason: SalaryReason;
  note: string | null;
  created_at: string;
}

export interface EquityGrant {
  id: string;
  grant_date: string;
  shares: number;
  created_at: string;
}

export interface ManagerSummary {
  id: string;
  employee_no: string;
  first_name: string;
  last_name: string;
}

export interface EmployeeListItem {
  id: string;
  employee_no: string;
  first_name: string;
  last_name: string;
  email: string;
  country: Country;
  department: string;
  level: string;
  employment_type: EmploymentType;
  status: EmployeeStatus;
  hire_date: string;
  manager_id: string | null;
  current_salary: CurrentSalary | null;
  band_position: BandPosition | null;
}

export interface EmployeeListResponse {
  items: EmployeeListItem[];
  page: number;
  size: number;
  total: number;
}

export interface EmployeeDetail {
  id: string;
  employee_no: string;
  first_name: string;
  last_name: string;
  email: string;
  country: Country;
  department_id: number;
  department: string;
  level_id: number;
  level: string;
  employment_type: EmploymentType;
  status: EmployeeStatus;
  hire_date: string;
  manager: ManagerSummary | null;
  direct_reports_count: number;
  current_salary: CurrentSalary | null;
  band_position: BandPosition | null;
  total_shares: number;
  salary_changes: SalaryChange[];
  equity_grants: EquityGrant[];
}

export interface EmployeeUpdate {
  department_id?: number;
  level_id?: number;
  manager_id?: string | null;
  employment_type?: EmploymentType;
  status?: EmployeeStatus;
}

export interface SalaryChangeCreate {
  effective_date: string;
  amount: string;
  currency_code: Currency;
  reason: SalaryReason;
  note?: string | null;
}

export interface EquityGrantCreate {
  grant_date: string;
  shares: number;
}

// --- Analytics -----------------------------------------------------------

export interface EmployeeFilters {
  country?: Country;
  department_id?: number;
  level_id?: number;
  employment_type?: EmploymentType;
  status?: EmployeeStatus;
}

export interface HeadcountByResult {
  rows: { dimension: string; count: number }[];
  dimension: Dimension;
  total: number;
}

export interface AvgSalaryByResult {
  rows: {
    dimension: string;
    avg_salary_usd: string;
    median_salary_usd: string;
    count: number;
  }[];
  dimension: Dimension;
}

export interface DistributionBucket {
  label: string;
  lower_usd: number;
  upper_usd: number | null;
  count: number;
}

export interface SalaryDistributionResult {
  buckets: DistributionBucket[];
  total: number;
}

export interface TopEarner {
  id: string;
  employee_no: string;
  first_name: string;
  last_name: string;
  country: Country;
  department: string;
  level: string;
  amount_usd: string;
  amount_native: string;
  currency_code: string;
}

export interface TopEarnersResult {
  rows: TopEarner[];
}

export interface BandSummary {
  below: number;
  within: number;
  above: number;
}

export interface OutOfBandEmployee {
  id: string;
  employee_no: string;
  first_name: string;
  last_name: string;
  country: Country;
  department: string;
  level: string;
  amount: string;
  currency_code: string;
  band_min: string;
  band_max: string;
  band_position: BandPosition;
}

export interface CompRatioVsBandResult {
  summary: BandSummary;
  out_of_band: OutOfBandEmployee[];
}

export interface RaiseEvent {
  id: string;
  employee_id: string;
  employee_no: string;
  first_name: string;
  last_name: string;
  country: Country;
  department: string;
  level: string;
  effective_date: string;
  amount: string;
  currency_code: string;
  amount_usd: string;
  reason: SalaryReason;
  note: string | null;
}

export interface RaisesInPeriodResult {
  rows: RaiseEvent[];
  count: number;
  start: string;
  end: string;
}

export interface HeadcountChangeRow {
  dimension: string;
  before_start: number;
  hired_in_period: number;
  total_through_end: number;
}

export interface HeadcountChangeResult {
  rows: HeadcountChangeRow[];
  dimension: Dimension;
  start: string;
  end: string;
}
