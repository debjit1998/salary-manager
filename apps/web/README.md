# salary-manager-web

Next.js 15 (App Router) + Tailwind + shadcn/ui + TanStack Query + axios
+ AgGrid. The frontend for the salary manager assessment.

## Run locally

Backend has to be up first:

```bash
cd ../api
docker compose -f docker-compose.dev.yml up -d
```

Then in this directory:

```bash
cd apps/web
cp .env.example .env.local        # default API URL is fine
npm install
npm run dev
```

Visit http://localhost:3000 — middleware bounces you to `/login`. Use
the seeded HR credentials (`hr@acme.org` / the password you set in
`apps/api/.env`, default `acme-demo-2026`).

## Layout

```
app/                                 # Next.js App Router
├── layout.tsx                       # Root: Providers, font, body
├── page.tsx                         # → redirects to /dashboard
├── globals.css                      # Tailwind + shadcn vars + AgGrid theme overrides
├── login/page.tsx
└── (authed)/                        # Route group — middleware-gated
    ├── layout.tsx                   # Sidebar shell, h-screen + overflow-hidden
    ├── dashboard/page.tsx
    ├── employees/page.tsx           # AgGrid list with URL-synced multi-select filters
    └── employees/[id]/page.tsx      # Detail page (cards + timeline + history + sheets)
components/
├── ui/                              # shadcn primitives (button, table, popover, …)
├── nav/                             # Sidebar, user menu
└── employees/                       # Domain components
    ├── employee-grid.tsx            # AgGrid wrapper + column defs + cell renderers
    ├── employee-grid-toolbar.tsx    # Search + 'N results' + ‹ x / y › pagination
    ├── column-header.tsx            # Custom AgGrid header — sort chevron + filter icon + count badge
    ├── column-filter.tsx            # Per-column multi-select popover (checkboxes + Clear)
    ├── employees-context.tsx        # React context for state + update callback
    ├── types.ts                     # EmployeeQueryState, EMPLOYEES_RETURN_KEY
    ├── band-badge.tsx, country-flag.tsx, salary-timeline-chart.tsx
    ├── edit-employee-sheet.tsx, add-salary-change-sheet.tsx,
    └── add-equity-grant-sheet.tsx   # RHF + Zod slide-in forms
lib/
├── api/                             # axios client + endpoint wrappers
│   ├── client.ts                    # withCredentials, 401 → /login, paramsSerializer
│   ├── auth.ts, employees.ts, analytics.ts, lookups.ts
├── hooks/                           # React Query hooks
│   ├── use-auth.ts, use-employees.ts, use-lookups.ts
├── utils.ts                         # shadcn `cn()`
└── format.ts                        # currency / date / ratio formatting
types/api.ts                         # TypeScript mirror of Pydantic schemas
middleware.ts                        # cookie-existence auth gate
```

## Stack

- **next 15** — App Router; client components throughout (this is a
  data-driven HR tool, not content-driven; SEO doesn't matter)
- **axios** — `lib/api/client.ts` sets `withCredentials`, 401-redirects,
  and uses `paramsSerializer: { indexes: null }` to write array params
  as repeated keys (`?country=US&country=UK`) — what FastAPI expects
- **@tanstack/react-query v5** — server-state cache; `QueryClient`
  mounted in `app/providers.tsx`. `keepPreviousData` on the employees
  list so the table doesn't blink during page/filter changes
- **ag-grid-community v34** — the employees list grid. Built-in sort +
  filter are disabled (`sortable: false`); the custom header drives
  URL-synced sort and opens a popover for filters, so everything stays
  server-driven
- **recharts** — salary timeline chart on the detail page (dashboard
  charts in Task #11)
- **react-hook-form + zod** — slide-in forms (edit profile / record
  raise / record grant)
- **sonner** — toast notifications
- **lucide-react** — icons

## Employee grid (`/employees`)

- Toolbar: global filter icon (employment type) + debounced search input
  + `N results` + `‹ page / total ›` paginator
- Per-column **multi-select** filters via column header icon: Country,
  Department, Level, Band position. Selected count shows as a badge on
  the filter icon
- Sortable columns toggle asc → desc → off on header click
- Everything serialises to the URL — `?country=US&country=UK&sort=-hire_date&page=3`
  is shareable / refresh-safe
- Row click navigates to `/employees/{id}`
- The list page mirrors its current `?search` into sessionStorage so the
  detail page's "Back to employees" link restores filters / sort / page
- Vertical centering and outer-border removal are scoped to
  `.ag-theme-quartz` overrides in `globals.css`

## Auth flow

1. Any request → middleware checks for a `session` cookie (existence
   only — the BE owns crypto validation).
2. Missing cookie → redirect to `/login`.
3. Login form posts JSON to FastAPI `/auth/login` with
   `withCredentials: true`. BE sets the httpOnly cookie.
4. axios response interceptor: any 401 on a non-login URL forces a
   client-side redirect to `/login` (catches expired sessions during
   normal navigation).
5. `useMe()` is the single source of truth for "am I authed?" — used
   by the `(authed)` layout for the gate and by `<UserMenu />` for the
   header.

## Adding more shadcn components

Run `npx shadcn@latest add <name>` in this directory — they're
copy-pasted into `components/ui/`. The init has already been done
(`components.json` is in place).
