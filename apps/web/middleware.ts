import { NextResponse, type NextRequest } from "next/server";

/** Light gate: existence-of-cookie check only. Cryptographic validation
 *  lives on the backend — `/auth/me` is the source of truth in the
 *  authed layout. This middleware just stops obvious unauthed deep-links
 *  from rendering the authed shell briefly before the BE redirect.
 */
export function middleware(req: NextRequest) {
  const isAuthed = req.cookies.has("session");
  const { pathname } = req.nextUrl;

  if (!isAuthed && pathname !== "/login") {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }
  if (isAuthed && pathname === "/login") {
    const url = req.nextUrl.clone();
    url.pathname = "/dashboard";
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  // Only match real pages — skip Next.js internals, static assets, the
  // health endpoint, etc.
  matcher: ["/((?!_next/|api/|favicon.ico|robots.txt).*)"],
};
