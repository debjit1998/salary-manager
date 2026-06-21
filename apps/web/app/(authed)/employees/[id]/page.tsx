import type { Metadata } from "next";

import { EmployeeDetailView } from "./view";

// Server-side metadata is a static fallback — the client view sets the
// document title to the employee's name once the API responds.
export const metadata: Metadata = {
  title: "Employee",
  description:
    "Profile, compensation history, equity grants, and salary timeline for a single employee.",
};

export default function EmployeeDetailPage() {
  return <EmployeeDetailView />;
}
