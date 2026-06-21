import { api } from "./client";
import type {
  AvgSalaryByResult,
  CompRatioVsBandResult,
  Dimension,
  EmployeeFilters,
  HeadcountByResult,
  HeadcountChangeResult,
  RaisesInPeriodResult,
  SalaryDistributionResult,
  TopEarnersResult,
} from "@/types/api";

export const analyticsApi = {
  headcountBy: (dimension: Dimension, filters: EmployeeFilters = {}) =>
    api
      .get<HeadcountByResult>("/analytics/headcount-by", {
        params: { dimension, ...filters },
      })
      .then((r) => r.data),

  avgSalaryBy: (dimension: Dimension, filters: EmployeeFilters = {}) =>
    api
      .get<AvgSalaryByResult>("/analytics/avg-salary-by", {
        params: { dimension, ...filters },
      })
      .then((r) => r.data),

  salaryDistribution: (filters: EmployeeFilters = {}) =>
    api
      .get<SalaryDistributionResult>("/analytics/salary-distribution", {
        params: filters,
      })
      .then((r) => r.data),

  topEarners: (n = 10, filters: EmployeeFilters = {}) =>
    api
      .post<TopEarnersResult>("/analytics/top-earners", { n, filters })
      .then((r) => r.data),

  compRatioVsBand: (filters: EmployeeFilters = {}) =>
    api
      .get<CompRatioVsBandResult>("/analytics/comp-ratio-vs-band", {
        params: filters,
      })
      .then((r) => r.data),

  raisesInPeriod: (start: string, end: string, filters: EmployeeFilters = {}) =>
    api
      .post<RaisesInPeriodResult>("/analytics/raises-in-period", {
        start,
        end,
        filters,
      })
      .then((r) => r.data),

  headcountChange: (start: string, end: string, dimension: Dimension) =>
    api
      .post<HeadcountChangeResult>("/analytics/headcount-change", {
        start,
        end,
        dimension,
      })
      .then((r) => r.data),
};
