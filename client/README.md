# AI Governance Console — Frontend

Next.js 15 frontend for the [AI Governance Console](../README.md) backend. It turns the
compliance API into something a risk officer can actually use: register AI systems, see
which jurisdictions apply and why, read policy findings with the article and the fix, and
produce audit-ready evidence packages.

## Stack

Next.js 15 (App Router) · TypeScript · Tailwind CSS 3 · shadcn/ui · TanStack Query ·
Zustand · Recharts · React Hook Form + Zod · next-themes · sonner · lucide-react

---

## Running it

### With Docker Compose (recommended)

From the **repository root**, this brings up the API, worker, PostgreSQL, Redis, OPA,
MinIO and this client together:

```bash
cp .env.example .env
docker compose up --build
```

Then open <http://localhost:3000>.

This is the recommended path because the client also proxies evidence downloads, which
needs it on the same network as object storage (see [Evidence downloads](#evidence-downloads)).

### Standalone dev server

With the backend already running (`docker compose up -d api` at the repo root):

```bash
cd client
npm install
cp .env.example .env.local
npm run dev
```

<http://localhost:3000>. The backend's default `CORS_ORIGINS` already allows this origin.

### Scripts

| Command | Does |
| --- | --- |
| `npm run dev` | dev server with hot reload |
| `npm run build` | production build |
| `npm start` | serve the production build |
| `npm run lint` | ESLint |
| `npm run typecheck` | `tsc --noEmit` |

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | API base URL **as the browser sees it**. Baked into the bundle at build time. |
| `INTERNAL_API_URL` | falls back to the above | API base URL as the Next.js **server** sees it. Only differs under Compose, where it is `http://api:8000`. |

## Signing in

The backend decides whether credentials are required, and the client adapts by calling
`GET /api/v1/auth/mode` on boot.

- **Auth enabled** (default) — you get a login page. Seeded demo accounts:

  | Email | Role |
  | --- | --- |
  | `admin@aigov.example.com` | admin |
  | `risk@aigov.example.com` | risk officer |
  | `viewer@aigov.example.com` | viewer |

  All use the password `ChangeMe123!`.

- **Auth disabled** (`AUTH_DISABLED=true` on the backend) — the login page is skipped
  entirely and every request runs as the backend's system principal, which holds the
  admin role. A warning badge appears in the top bar, because in that mode anyone who can
  reach the port has full administrative control.

Actions are hidden for roles that cannot perform them (a `viewer` sees no "Add system" or
"Run policy checks" buttons). That is presentation only — the backend enforces the same
matrix and would answer `403` regardless.

### A note on token storage

Access and refresh tokens are kept in `localStorage` via Zustand's `persist`. That is the
usual trade-off for a bearer-token SPA: the session survives a reload, at the cost of being
readable by injected script. The backend keeps access tokens short-lived (30 minutes) and
the client refreshes them transparently, single-flight, on the first `401`.

## Pages

| Route | What it does |
| --- | --- |
| `/login` | Sign in. Skipped when the backend has auth disabled. |
| `/dashboard` | Compliance score, risk distribution, compliance by jurisdiction, recent failures, systems needing attention. |
| `/systems` | Searchable, filterable inventory. |
| `/systems/new` · `/systems/[id]/edit` | Register or update a system. |
| `/systems/[id]` | **The core page.** Six tabs: Overview, Jurisdictions, Risk, Policy checks, Evidence, Activity — plus Classify / Run policy checks / Generate evidence. |
| `/evidence` | Every evidence package across the portfolio, with downloads. |
| `/audit-logs` | Admin only. Append-only audit trail with before/after values and request fingerprint. |
| `/policies` · `/jurisdictions` | Read-only views of the configured rules and regimes. |
| `/users` | Admin only. User list and creation. |

## How it is put together

```
app/          routes; (auth) and (dashboard) groups, plus the evidence download proxy
components/   ui/ (shadcn), layout/, systems/, dashboard/, shared/
hooks/        one TanStack Query hook module per resource
lib/          api.ts (the only place that talks to the backend), errors, constants, format
stores/       Zustand: auth session, UI preferences
types/        hand-written mirror of the backend's OpenAPI schema
```

**`lib/api.ts` is the single integration point.** It attaches the bearer token, unwraps the
`{success, data}` envelope every `/api/v1` route returns, converts
`{success: false, error}` into a typed `ApiError`, and refreshes an expired token once
before retrying. No component builds a URL or unwraps a payload.

**`lib/constants.ts` mirrors the backend's vocabularies.** Use cases like
`employment_screening` and region codes like `US-CA` are not cosmetic — they drive Annex III
matching and jurisdiction detection. The forms offer the real values as suggestions while
still accepting free text.

**Status colour is defined once.** The badge components in `components/shared/status-badges.tsx`
map a domain value (risk tier, policy result, severity) to a colour token, so "red means
fail" holds everywhere and in both themes. Call sites never pass a colour.

## Evidence downloads

Evidence packages live in object storage, and the backend presigns their URLs against its
own view of MinIO — `http://minio:9000` under Compose. That hostname only resolves inside
the Compose network, so linking a browser straight at it gives a dead download. The host
cannot simply be rewritten either: S3 signatures cover the `Host` header.

So downloads go through a Next route handler
(`app/api/evidence/[systemId]/[packageId]/route.ts`) that runs server-side, where
`minio:9000` does resolve, fetches the object with its signature intact, and streams the
bytes back. The browser sends its bearer token with that request, so the file is fetched
with `fetch` and saved as a blob rather than through a plain `<a href>`, which cannot carry
an `Authorization` header.

**Running `npm run dev` on the host instead of in Compose?** Then the Next server is not on
the Compose network either. Add an alias so the presigned host resolves to the published
MinIO port:

```
127.0.0.1 minio
```

in `/etc/hosts`. Without it, downloads return a 502 explaining exactly this.

## Design notes

- **Dark and light** via `next-themes`, toggled in the top bar. Chart colours resolve from
  CSS variables, so they follow the theme.
- **Three states everywhere.** Every list has a skeleton shaped like its final layout, an
  empty state that says what to do next, and an error state with a retry.
- **Failures come first.** On the Policy checks tab, failing checks sort to the top and
  open by default — a compliance officer should not have to hunt for the problem. Every
  finding shows its article, severity, explanation and a "how to fix" panel.
- **Desktop-first, responsive.** The sidebar collapses into a sheet below `lg`.

## Disclaimer

This interface helps track and document compliance work. It is not legal advice, and it
does not certify compliance with any regulation. Every finding cites its source so a
qualified person can verify it.
