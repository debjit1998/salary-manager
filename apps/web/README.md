# salary-manager-web

Next.js 15 (App Router) + Tailwind + shadcn/ui + TanStack Query + axios.
The frontend for the salary manager assessment.

## Run locally

The backend has to be up first:

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
the seeded HR credentials (`hr@acme.org` and whatever password you set
in `apps/api/.env`, default `acme-demo-2026`).

## Layout

```
app/                                 # Next.js App Router
├── layout.tsx                       # Root: Providers, font, body
├── page.tsx                         # → redirects to /dashboard
├── login/page.tsx
└── (authed)/                        # Route group — middleware-gated
    ├── layout.tsx                   # Sidebar shell, /auth/me check
    ├── dashboard/page.tsx
    ├── employees/page.tsx
    └── employees/[id]/page.tsx
components/
├── ui/                              # shadcn primitives
└── nav/                             # Sidebar, user menu
lib/
├── api/                             # axios client + endpoint wrappers
├── hooks/                           # React Query hooks
├── utils.ts                         # shadcn `cn()`
└── format.ts                        # currency / date / ratio formatting
types/api.ts                         # TypeScript types mirroring Pydantic
middleware.ts                        # cookie-existence auth gate
```

## Adding more shadcn components

Run `npx shadcn@latest add <name>` in this directory — they're
copy-pasted into `components/ui/`. The init has already been done
(`components.json` is in place).

## Stack

- **next** 15 — App Router
- **axios** — HTTP client; `lib/api/client.ts` sets `withCredentials`
  and routes 401s to `/login`
- **@tanstack/react-query** — server-state cache; one `QueryClient`
  per app instance, mounted in `app/providers.tsx`
- **@tanstack/react-table** — used by the employees list page (Task #10)
- **recharts** — used by the dashboard (Task #11)
- **react-hook-form** + **zod** — for the salary-change / employee
  edit forms (Task #10)
- **sonner** — toasts (mounted by `<Toaster />` in providers)
- **lucide-react** — icons

## Auth flow

1. Any request → middleware checks for a `session` cookie (existence
   only — the BE owns crypto validation).
2. Missing cookie → redirect to `/login`.
3. Login form posts JSON to the FastAPI `/auth/login` with
   `withCredentials: true`. BE sets the httpOnly cookie.
4. axios response interceptor: any 401 on a non-login URL forces a
   client-side redirect to `/login` (catches expired sessions during
   normal navigation).
5. `useMe()` is the single source of truth for "am I authed?" — used
   by the (authed) layout for the gate and by `<UserMenu />` to show
   the current email.
