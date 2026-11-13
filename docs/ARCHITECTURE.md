# ReTurn architecture

## Runtime topology

```text
Browser
  │  same-origin fetch, HttpOnly session cookie + CSRF header
  ▼
Next.js 15 App Router (server components + client components)
  │  /api/v1/* rewrite (FLASK_API_URL, server-only)
  │  server components fetch API_INTERNAL_URL and forward the user cookie
  ▼
Flask 3 /api/v1  ── SQLAlchemy ── PostgreSQL (Alembic-managed)
  │
  ├─ rule-based matching + insertion heuristic
  ├─ OSRM table/route (short timeout) → labelled deterministic estimate on failure
  └─ server-side sessions, CSRF, RBAC, rate limits, transactional dispatch
```

Leaflet is imported only inside a `"use client"` component in a browser effect. Server components never touch `window` or the map library.

## Backend modules

| Module | Responsibility |
|---|---|
| `app/__init__.py` | factory, blueprints, security pipeline, headers, cache prevention |
| `app/config.py` | environment config, matching defaults, sustainability factors |
| `app/models.py` | relational schema, indexes, partial unique reservation index |
| `app/domain.py` | status vocabularies, legal parcel transitions, codes |
| `app/security.py` | Argon2id, sessions, CSRF, role decorators, rate limiter |
| `app/access.py` | request/batch ownership and contact boundaries |
| `app/serializers.py` | role-aware JSON, no cross-customer leakage |
| `app/api/*` | auth, requests, matching, batches, parcels, partners, customers, issues, notifications, analytics, admin |
| `app/services/matching.py` | feasibility simulation, insertion search, explanations, savings |
| `app/services/routing.py` | OSRM matrix/geometry, estimated fallback, labels |
| `app/services/dispatch.py` | commit/offer/accept/decline/reassign/cancel/start/parcel events, audits, notifications |
| `app/services/analytics.py` | KPIs and estimated impact with methodology |
| `app/services/seed.py` | deterministic fictional scenario |

## Data model

```text
users ──1:1── partner_profiles
  │
  ├──1:N── delivery_requests ──1:1── parcels ──1:N── tracking_events
  │             │  │
  │             │  ├──1:1── return_details (authorised hub, reference)
  │             │  └──1:1── recipient_details (recipient contact)
  │             │
  │             └──N:M via batch_requests (active reservation + released history)
  │                        │
  │                        └── delivery_batches ──1:N── batch_stops (ordered, load snapshot)
  │                              ├──1:N── batch_assignments (offer/accept/decline/reassign history)
  │                              └──1:N── audit_events (through entity id)
  ├──1:N── user_sessions
  ├──1:N── notifications
  └──1:N── issue_reports

locations ── pickup/destination FKs on each request
matching_runs ── full preview JSON (params, groups, rejections)
audit_events ── actor, action, entity, reason, metadata
```

Key constraints:

- `UNIQUE(parcels.request_id)`, `UNIQUE(users.email)`, `UNIQUE(user_sessions.token_hash)`.
- `UNIQUE(batch_stops.batch_id, sequence)`.
- **Partial unique index** `uq_batch_requests_active_request ON batch_requests(request_id) WHERE released_at IS NULL` — the database, not application logic, guarantees one active batch per request.
- Indexes on request status/window, owner+status, batch status, partner availability/verification, parcel status and notification read state.

## Matching flow

```text
pending requests (status=pending_matching, no active reservation)
  │
  ├─ hard prefilter: pickup radius
  ├─ build estimated/OSRM matrix
  ├─ for each seed → for each candidate:
  │     for each pickup insert position i:
  │        for each drop-off position j > i:
  │           simulate itinerary:
  │             travel → wait → pickup window check → load capacity
  │             → drop-off deadline → load release → service time
  │           reject with a reason code if any hard rule fails
  │     keep lowest-distance feasible insertion
  ├─ group ≥ 2 → savings vs same-basis separate-trip baseline
  │     reject if raw saving ≤ 0 or < configured minimum
  └─ re-solve selected group with build_group() for the proposal payload
```

Commit calls `quote_selected_requests()` again, then locks the request rows with `SELECT … FOR UPDATE`, verifies statuses and reservations, recalculates the group, stores the batch/stops/reservation rows and commits once. Unique-index conflicts become a `409`.

## Dispatch state machines

```text
Batch:     proposed ──offer──▶ offered ──accept──▶ accepted ──start──▶ in_progress ──all terminal──▶ completed
              │                  │                    │
              │                  ├─decline──▶ declined (re-offerable)
              └──── cancel ───────┴────────────▶ cancelled (releases requests)

Request:   pending_matching ──commit──▶ batched ──accept──▶ assigned ──start──▶ in_progress ──delivered──▶ completed
Parcel:    pending ─▶ assigned ─▶ partner_accepted ─▶ pickup_arrived ─▶ picked_up ─▶ in_transit ─▶ delivered
                                                    └──────────────── failed (reason required → issue) ────────────┘
```

## Authentication / CSRF sequence

```text
Browser GET /api/v1/auth/csrf
  → Flask sets rt_csrf (readable, SameSite=Lax)
Browser POST /auth/login with X-CSRF-Token = cookie value
  → Flask verifies double-submit, validates credentials
  → creates session row (token hash + session CSRF token)
  → sets HttpOnly rt_session + rotates rt_csrf cookie
Browser mutating request with X-CSRF-Token
  → header == rt_csrf cookie == session.csrf_token
Server components forward rt_session from cookies() to Flask via API_INTERNAL_URL
  → Flask resolves the identity and enforces ownership/RBAC
```

## Frontend design/architecture

- `/customer`, `/partner`, `/admin` layouts call `requireUser(role)`, which redirects to `/auth` or `/forbidden`. This is convenience only; Flask enforces every permission.
- Sensitive data is fetched with `cache: "no-store"` per user and dynamic rendering; no role page is statically cached.
- Server components compose page data. Client components own forms, dialogs, map, notifications and dispatch actions.
- Notifications use TanStack Query; API calls use a typed client that bootstraps CSRF before unsafe methods.
- Design tokens are CSS variables mirrored into Tailwind; the route-thread motif, pickup circles and drop-off squares are consistent across marketing, maps and timelines.
