import { redirect } from "next/navigation";

/** Root `/` redirects straight to the dashboard. Auth middleware will
 *  bounce unauthenticated visitors to /login. */
export default function Page() {
  redirect("/dashboard");
}
