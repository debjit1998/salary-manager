"use client";

import { Sparkles } from "lucide-react";
import { useState } from "react";

import { ChartCard } from "@/components/dashboard/chart-card";
import {
  ChartFilterDialog,
  type ChartFilterKey,
} from "@/components/dashboard/chart-filter-dialog";
import { DashboardStats } from "@/components/dashboard/dashboard-stats";
import { NLQueryDrawer } from "@/components/dashboard/nl-query-drawer";
import { AvgSalaryViz } from "@/components/dashboard/viz/avg-salary-viz";
import { BandViz } from "@/components/dashboard/viz/band-viz";
import { DistributionViz } from "@/components/dashboard/viz/distribution-viz";
import { HeadcountViz } from "@/components/dashboard/viz/headcount-viz";
import { TopEarnersViz } from "@/components/dashboard/viz/top-earners-viz";
import { Button } from "@/components/ui/button";
import {
  useAvgSalaryBy,
  useCompRatioVsBand,
  useHeadcountBy,
  useSalaryDistribution,
  useTopEarners,
} from "@/lib/hooks/use-analytics";
import type { EmployeeFilters } from "@/types/api";

// Filters each chart supports. The dimension axis (or output) of each
// chart is intentionally excluded so the dialog doesn't expose a
// redundant / circular filter.
const FILTERS: Record<string, ChartFilterKey[]> = {
  headcountByDept: [
    "level_id",
    "country",
    "employment_type",
    "band_position",
    "salary_band",
  ],
  headcountByCountry: [
    "level_id",
    "department_id",
    "employment_type",
    "band_position",
    "salary_band",
  ],
  avgByLevel: [
    "department_id",
    "country",
    "employment_type",
    "band_position",
    "salary_band",
  ],
  distribution: [
    "level_id",
    "department_id",
    "country",
    "employment_type",
    "band_position",
    // salary_band intentionally omitted — filtering a distribution by
    // salary range would collapse the chart onto itself.
  ],
  topEarners: [
    "level_id",
    "department_id",
    "country",
    "employment_type",
    "band_position",
    "salary_band",
  ],
  bandSummary: [
    "level_id",
    "department_id",
    "country",
    "employment_type",
    "salary_band",
    // band_position intentionally omitted — it IS the output of this chart.
  ],
};

export function DashboardView() {
  const [deptFilters, setDeptFilters] = useState<EmployeeFilters>({});
  const [countryFilters, setCountryFilters] = useState<EmployeeFilters>({});
  const [levelFilters, setLevelFilters] = useState<EmployeeFilters>({});
  const [distFilters, setDistFilters] = useState<EmployeeFilters>({});
  const [topEarnersFilters, setTopEarnersFilters] = useState<EmployeeFilters>(
    {},
  );
  const [bandFilters, setBandFilters] = useState<EmployeeFilters>({});

  const headcountByDept = useHeadcountBy("department", deptFilters);
  const headcountByCountry = useHeadcountBy("country", countryFilters);
  const avgByLevel = useAvgSalaryBy("level", levelFilters);
  const distribution = useSalaryDistribution(distFilters);
  const topEarners = useTopEarners(10, topEarnersFilters);
  const bandSummary = useCompRatioVsBand(bandFilters);

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6 lg:p-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Dashboard
        </h1>
        <NLQueryDrawer>
          <Button variant="default">
            <Sparkles className="size-4" />
            Ask AI
          </Button>
        </NLQueryDrawer>
      </div>

      <DashboardStats />

      {/* Row 1: Headcount by Dept + Salary distribution */}
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Headcount by department"
          isLoading={headcountByDept.isLoading}
          isError={headcountByDept.isError}
          filter={
            <ChartFilterDialog
              availableFilters={FILTERS.headcountByDept}
              value={deptFilters}
              onChange={setDeptFilters}
            />
          }
        >
          {headcountByDept.data && (
            <HeadcountViz data={headcountByDept.data.rows} layout="horizontal" />
          )}
        </ChartCard>
        <ChartCard
          title="Salary distribution"
          description="USD, current annual base"
          isLoading={distribution.isLoading}
          isError={distribution.isError}
          filter={
            <ChartFilterDialog
              availableFilters={FILTERS.distribution}
              value={distFilters}
              onChange={setDistFilters}
            />
          }
        >
          {distribution.data && (
            <DistributionViz data={distribution.data.buckets} />
          )}
        </ChartCard>
      </div>

      {/* Row 2: Avg salary by Level + Headcount by Country */}
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Average salary by level (USD)"
          isLoading={avgByLevel.isLoading}
          isError={avgByLevel.isError}
          filter={
            <ChartFilterDialog
              availableFilters={FILTERS.avgByLevel}
              value={levelFilters}
              onChange={setLevelFilters}
            />
          }
        >
          {avgByLevel.data && <AvgSalaryViz data={avgByLevel.data.rows} />}
        </ChartCard>
        <ChartCard
          title="Headcount by country"
          isLoading={headcountByCountry.isLoading}
          isError={headcountByCountry.isError}
          filter={
            <ChartFilterDialog
              availableFilters={FILTERS.headcountByCountry}
              value={countryFilters}
              onChange={setCountryFilters}
            />
          }
        >
          {headcountByCountry.data && (
            <HeadcountViz
              data={headcountByCountry.data.rows}
              layout="vertical"
            />
          )}
        </ChartCard>
      </div>

      {/* Row 3: Top earners + Comp band breakdown */}
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Top 10 earners"
          isLoading={topEarners.isLoading}
          isError={topEarners.isError}
          contentClassName="p-0"
          filter={
            <ChartFilterDialog
              availableFilters={FILTERS.topEarners}
              value={topEarnersFilters}
              onChange={setTopEarnersFilters}
            />
          }
        >
          {topEarners.data && <TopEarnersViz rows={topEarners.data.rows} />}
        </ChartCard>
        <ChartCard
          title="Comp band positions"
          description="Are we paying people within their level's band?"
          isLoading={bandSummary.isLoading}
          isError={bandSummary.isError}
          filter={
            <ChartFilterDialog
              availableFilters={FILTERS.bandSummary}
              value={bandFilters}
              onChange={setBandFilters}
            />
          }
        >
          {bandSummary.data && (
            <BandViz
              summary={bandSummary.data.summary}
              list={bandSummary.data.out_of_band}
              compact
            />
          )}
        </ChartCard>
      </div>
    </div>
  );
}
