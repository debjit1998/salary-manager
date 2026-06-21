"use client";

import { AgGridReact } from "ag-grid-react";
import {
  AllCommunityModule,
  ModuleRegistry,
  type ColDef,
  type GetRowIdParams,
  type ICellRendererParams,
  type RowClickedEvent,
} from "ag-grid-community";
import { useRouter } from "next/navigation";
import { useMemo } from "react";

import { formatCurrency, formatDate } from "@/lib/format";
import type { EmployeeListItem } from "@/types/api";

import { BandBadge } from "./band-badge";
import { EmployeeColumnHeader } from "./column-header";
import { CountryFlag } from "./country-flag";

// Ag-grid CSS — route-scoped because the grid is only used on /employees
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-quartz.css";

// Register community modules once per app load.
ModuleRegistry.registerModules([AllCommunityModule]);

interface Props {
  rows: EmployeeListItem[];
  isLoading: boolean;
}

const NameCell = (p: ICellRendererParams<EmployeeListItem>) => {
  const r = p.data!;
  return (
    <span className="font-medium text-slate-900">
      {r.first_name} {r.last_name}
    </span>
  );
};

const EmailCell = (p: ICellRendererParams<EmployeeListItem>) => (
  <span className="text-slate-500">{p.data!.email}</span>
);

const CountryCell = (p: ICellRendererParams<EmployeeListItem>) => (
  <CountryFlag country={p.data!.country} />
);

const LevelCell = (p: ICellRendererParams<EmployeeListItem>) => (
  <span className="font-mono text-xs text-slate-600">{p.data!.level}</span>
);

const SalaryCell = (p: ICellRendererParams<EmployeeListItem>) => {
  const cs = p.data!.current_salary;
  if (!cs) return <span className="text-slate-400">—</span>;
  return (
    <span className="block text-right tabular-nums text-slate-900">
      {formatCurrency(Number(cs.amount_usd))}
    </span>
  );
};

const BandCell = (p: ICellRendererParams<EmployeeListItem>) => (
  <BandBadge position={p.data!.band_position} />
);

const HiredCell = (p: ICellRendererParams<EmployeeListItem>) => (
  <span className="text-slate-500">{formatDate(p.data!.hire_date)}</span>
);

const EmployeeNoCell = (p: ICellRendererParams<EmployeeListItem>) => (
  <span className="font-mono text-xs text-slate-500">
    {p.data!.employee_no}
  </span>
);

export function EmployeeGrid({ rows, isLoading }: Props) {
  const router = useRouter();

  const columnDefs = useMemo<ColDef<EmployeeListItem>[]>(
    () => [
      {
        field: "employee_no",
        headerName: "ID",
        width: 130,
        cellRenderer: EmployeeNoCell,
        headerComponent: EmployeeColumnHeader,
        headerComponentParams: { displayName: "ID", sortKey: "employee_no" },
      },
      {
        field: "first_name",
        headerName: "Name",
        flex: 1.4,
        minWidth: 180,
        cellRenderer: NameCell,
        headerComponent: EmployeeColumnHeader,
        headerComponentParams: { displayName: "Name", sortKey: "last_name" },
      },
      {
        field: "email",
        headerName: "Email",
        flex: 1.6,
        minWidth: 220,
        cellRenderer: EmailCell,
        headerComponent: EmployeeColumnHeader,
        headerComponentParams: { displayName: "Email", sortKey: "email" },
      },
      {
        field: "country",
        headerName: "Country",
        width: 130,
        cellRenderer: CountryCell,
        headerComponent: EmployeeColumnHeader,
        headerComponentParams: { displayName: "Country", filterKey: "country" },
      },
      {
        field: "department",
        headerName: "Department",
        width: 170,
        headerComponent: EmployeeColumnHeader,
        headerComponentParams: {
          displayName: "Department",
          filterKey: "dept_id",
        },
      },
      {
        field: "level",
        headerName: "Level",
        width: 110,
        cellRenderer: LevelCell,
        headerComponent: EmployeeColumnHeader,
        headerComponentParams: {
          displayName: "Level",
          sortKey: "level",
          filterKey: "level_id",
        },
      },
      {
        field: "current_salary",
        headerName: "Salary (USD)",
        width: 160,
        cellRenderer: SalaryCell,
        cellClass: "ag-right-aligned-cell",
        headerClass: "ag-right-aligned-header",
        headerComponent: EmployeeColumnHeader,
        headerComponentParams: {
          displayName: "Salary (USD)",
          sortKey: "current_salary_usd",
          filterKey: "salary_band",
        },
      },
      {
        field: "band_position",
        headerName: "Band",
        width: 130,
        cellRenderer: BandCell,
        headerComponent: EmployeeColumnHeader,
        headerComponentParams: {
          displayName: "Band",
          filterKey: "band_position",
        },
      },
      {
        field: "hire_date",
        headerName: "Hired",
        width: 130,
        cellRenderer: HiredCell,
        headerComponent: EmployeeColumnHeader,
        headerComponentParams: { displayName: "Hired", sortKey: "hire_date" },
      },
    ],
    [],
  );

  const defaultColDef = useMemo<ColDef>(
    () => ({
      // Disable AgGrid's built-in sort + filter — we drive both from URL state.
      sortable: false,
      filter: false,
      suppressHeaderMenuButton: true,
      resizable: true,
      cellClass: "flex items-center",
    }),
    [],
  );

  function onRowClicked(e: RowClickedEvent<EmployeeListItem>) {
    if (!e.data) return;
    router.push(`/employees/${e.data.id}`);
  }

  return (
    <div className="ag-theme-quartz size-full">
      <AgGridReact<EmployeeListItem>
        rowData={isLoading && rows.length === 0 ? undefined : rows}
        columnDefs={columnDefs}
        defaultColDef={defaultColDef}
        headerHeight={40}
        rowHeight={44}
        suppressCellFocus
        suppressMultiSort
        getRowId={(p: GetRowIdParams<EmployeeListItem>) => p.data.id}
        onRowClicked={onRowClicked}
        overlayNoRowsTemplate='<span class="text-sm text-slate-500">No employees match your filters.</span>'
        overlayLoadingTemplate='<span class="text-sm text-slate-500">Loading employees…</span>'
      />
    </div>
  );
}
