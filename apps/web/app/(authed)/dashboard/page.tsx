"use client";

import { Sparkles } from "lucide-react";

import { ChartCard } from "@/components/dashboard/chart-card";
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

export default function DashboardPage() {
  const headcountByDept = useHeadcountBy("department");
  const headcountByCountry = useHeadcountBy("country");
  const avgByLevel = useAvgSalaryBy("level");
  const distribution = useSalaryDistribution();
  const topEarners = useTopEarners(10);
  const bandSummary = useCompRatioVsBand();

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
        >
          {avgByLevel.data && <AvgSalaryViz data={avgByLevel.data.rows} />}
        </ChartCard>
        <ChartCard
          title="Headcount by country"
          isLoading={headcountByCountry.isLoading}
          isError={headcountByCountry.isError}
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
        >
          {topEarners.data && <TopEarnersViz rows={topEarners.data.rows} />}
        </ChartCard>
        <ChartCard
          title="Comp band positions"
          description="Are we paying people within their level's band?"
          isLoading={bandSummary.isLoading}
          isError={bandSummary.isError}
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
