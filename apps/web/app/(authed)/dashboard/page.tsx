import type { Metadata } from "next";

import { DashboardView } from "./view";

export const metadata: Metadata = {
  title: "Dashboard",
  description:
    "Headcount, salary distribution, comp bands, and top earners — across the org. Ask the AI assistant a question in plain English.",
};

export default function DashboardPage() {
  return <DashboardView />;
}
