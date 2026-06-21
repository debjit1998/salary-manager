import type { Metadata } from "next";
import { Suspense } from "react";

import { EmployeesView } from "./view";

export const metadata: Metadata = {
  title: "Employees",
  description:
    "Browse, search, and filter the org. Current salary, level, comp band, and country for every employee.",
};

export default function EmployeesPage() {
  return (
    <Suspense fallback={null}>
      <EmployeesView />
    </Suspense>
  );
}
