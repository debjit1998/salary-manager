"use client";

import { useQuery } from "@tanstack/react-query";

import { analyticsApi } from "@/lib/api/analytics";
import type { Dimension, EmployeeFilters } from "@/types/api";

const STALE = 60 * 1000;

export function useSummary() {
  return useQuery({
    queryKey: ["analytics", "summary"],
    queryFn: analyticsApi.summary,
    staleTime: STALE,
  });
}

export function useHeadcountBy(
  dimension: Dimension,
  filters: EmployeeFilters = {},
) {
  return useQuery({
    queryKey: ["analytics", "headcount-by", dimension, filters],
    queryFn: () => analyticsApi.headcountBy(dimension, filters),
    staleTime: STALE,
  });
}

export function useAvgSalaryBy(
  dimension: Dimension,
  filters: EmployeeFilters = {},
) {
  return useQuery({
    queryKey: ["analytics", "avg-salary-by", dimension, filters],
    queryFn: () => analyticsApi.avgSalaryBy(dimension, filters),
    staleTime: STALE,
  });
}

export function useSalaryDistribution(filters: EmployeeFilters = {}) {
  return useQuery({
    queryKey: ["analytics", "salary-distribution", filters],
    queryFn: () => analyticsApi.salaryDistribution(filters),
    staleTime: STALE,
  });
}

export function useTopEarners(n = 10, filters: EmployeeFilters = {}) {
  return useQuery({
    queryKey: ["analytics", "top-earners", n, filters],
    queryFn: () => analyticsApi.topEarners(n, filters),
    staleTime: STALE,
  });
}

export function useCompRatioVsBand(filters: EmployeeFilters = {}) {
  return useQuery({
    queryKey: ["analytics", "comp-ratio-vs-band", filters],
    queryFn: () => analyticsApi.compRatioVsBand(filters),
    staleTime: STALE,
  });
}
