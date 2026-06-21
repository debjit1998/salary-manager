"use client";

import { Markdown } from "@/components/ui/markdown";
import type {
  AvgSalaryByResult,
  CompRatioVsBandResult,
  HeadcountByResult,
  HeadcountChangeResult,
  NLResponse,
  NLToolName,
  RaisesInPeriodResult,
  SalaryDistributionResult,
  TopEarnersResult,
} from "@/types/api";

import { AvgSalaryViz } from "./viz/avg-salary-viz";
import { BandViz } from "./viz/band-viz";
import { DistributionViz } from "./viz/distribution-viz";
import { HeadcountChangeViz } from "./viz/headcount-change-viz";
import { HeadcountViz } from "./viz/headcount-viz";
import { RaisesViz } from "./viz/raises-viz";
import { SqlTableViz } from "./viz/sql-table-viz";
import { TopEarnersViz } from "./viz/top-earners-viz";

const TOOL_LABEL: Record<NLToolName, string> = {
  headcount_by: "Headcount",
  avg_salary_by: "Average salary",
  salary_distribution: "Salary distribution",
  top_n_earners: "Top earners",
  comp_ratio_vs_band: "Comp band positions",
  raises_in_period: "Raises in period",
  headcount_change: "Headcount change",
};

interface Props {
  response: NLResponse;
}

export function NLAnswer({ response }: Props) {
  if (response.kind === "text") {
    return <Markdown>{response.text}</Markdown>;
  }
  if (response.kind === "error") {
    return (
      <p className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
        {response.error}
      </p>
    );
  }
  if (response.kind === "sql") {
    return (
      <SqlTableViz
        sql={response.sql}
        columns={response.columns}
        rows={response.rows}
      />
    );
  }

  // kind === "tool"
  return (
    <div className="space-y-3">
      <p className="text-xs uppercase tracking-wider text-slate-500">
        {TOOL_LABEL[response.tool] ?? response.tool}
      </p>
      <ToolViz tool={response.tool} result={response.result} />
    </div>
  );
}

function ToolViz({
  tool,
  result,
}: {
  tool: NLToolName;
  result: unknown;
}) {
  switch (tool) {
    case "headcount_by": {
      const r = result as HeadcountByResult;
      return <HeadcountViz data={r.rows} layout={r.rows.length <= 4 ? "vertical" : "horizontal"} />;
    }
    case "avg_salary_by": {
      const r = result as AvgSalaryByResult;
      return <AvgSalaryViz data={r.rows} />;
    }
    case "salary_distribution": {
      const r = result as SalaryDistributionResult;
      return <DistributionViz data={r.buckets} />;
    }
    case "top_n_earners": {
      const r = result as TopEarnersResult;
      return <TopEarnersViz rows={r.rows} targetCurrency={r.target_currency} />;
    }
    case "comp_ratio_vs_band": {
      const r = result as CompRatioVsBandResult;
      return <BandViz summary={r.summary} list={r.out_of_band} />;
    }
    case "raises_in_period": {
      const r = result as RaisesInPeriodResult;
      return <RaisesViz rows={r.rows} />;
    }
    case "headcount_change": {
      const r = result as HeadcountChangeResult;
      return <HeadcountChangeViz rows={r.rows} />;
    }
    default:
      return <pre className="text-xs">{JSON.stringify(result, null, 2)}</pre>;
  }
}
