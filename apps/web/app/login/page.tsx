import type { Metadata } from "next";

import { LoginView } from "./view";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to Salary Manager to manage compensation for the org.",
};

export default function LoginPage() {
  return <LoginView />;
}
