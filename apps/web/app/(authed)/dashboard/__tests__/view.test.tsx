/**
 * Smoke tests for the dashboard page view.
 *
 * The view fans out to 5 analytics hooks plus the NL drawer and the
 * stats card. We stub the leaf children to keep the test focused on the
 * page's own structure (title + 6 chart cards + Ask AI button) and we
 * mock the analytics hooks to return loading state so the cards render
 * their skeleton paths.
 */

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { DashboardView } from "../view";

// ---- Mocks --------------------------------------------------------------

// All five analytics hooks return loading. We don't care about the data
// shapes here — just that the page renders the surrounding chrome.
const loadingResult = { data: undefined, isLoading: true, isError: false };
vi.mock("@/lib/hooks/use-analytics", () => ({
  useHeadcountBy: () => loadingResult,
  useAvgSalaryBy: () => loadingResult,
  useSalaryDistribution: () => loadingResult,
  useTopEarners: () => loadingResult,
  useCompRatioVsBand: () => loadingResult,
}));

// The stats card and the NL drawer both pull their own data; stub them
// to keep the test hermetic.
vi.mock("@/components/dashboard/dashboard-stats", () => ({
  DashboardStats: () => <div data-testid="dashboard-stats" />,
}));
vi.mock("@/components/dashboard/nl-query-drawer", () => ({
  NLQueryDrawer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="nl-drawer">{children}</div>
  ),
}));
// Each chart card renders a ChartFilterDialog which itself calls
// useLookups (TanStack Query). Stub the dialog to avoid having to
// stand up a QueryClientProvider just for the smoke test.
vi.mock("@/components/dashboard/chart-filter-dialog", () => ({
  ChartFilterDialog: () => null,
}));

describe("DashboardView", () => {
  it("renders the page header with an Ask AI trigger", () => {
    render(<DashboardView />);
    expect(
      screen.getByRole("heading", { name: /Dashboard/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Ask AI/i })).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-stats")).toBeInTheDocument();
    expect(screen.getByTestId("nl-drawer")).toBeInTheDocument();
  });

  it("renders all six chart cards", () => {
    render(<DashboardView />);
    // The exact titles are part of the public surface — if any get
    // renamed without conscious thought, this test catches it.
    expect(screen.getByText("Headcount by department")).toBeInTheDocument();
    expect(screen.getByText("Salary distribution")).toBeInTheDocument();
    expect(
      screen.getByText("Average salary by level (USD)"),
    ).toBeInTheDocument();
    expect(screen.getByText("Headcount by country")).toBeInTheDocument();
    expect(screen.getByText("Top 10 earners")).toBeInTheDocument();
    expect(screen.getByText("Comp band positions")).toBeInTheDocument();
  });
});
