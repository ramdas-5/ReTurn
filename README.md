# ReTurn — Smart Reverse Delivery & Shared Logistics Platform

**One Route. Multiple Deliveries. Less Waste.**

ReTurn coordinates two distinct services — **product returns to an authorised return destination** and **ordinary parcel deliveries to a recipient's own address** — and searches for a genuinely feasible shared multi-stop route. It is a coordination and constrained route-planning application. ReTurn does not own courier vehicles, does not claim trained AI, and labels every distance/fuel/emissions figure as an **estimate**.

The core innovation is a real, explainable matching engine: separate requests become one ordered pickup/delivery itinerary only when windows, deadlines, precedence, capacity at every stop, handling, service area, detour and estimated savings all pass. Nearby requests are rejected with reasons when they are not compatible.

---

## 1. Stack (mandatory choices preserved)

| Layer | Implementation |
|---|---|
| Frontend | **Next.js 15 App Router + React 19 + TypeScript** (`frontend/`) |
| Styling | Tailwind CSS + ReTurn semantic tokens, Lucide icons, Plus Jakarta Sans / Inter / IBM Plex Mono |
| Forms & client data | React Hook Form + Zod, TanStack Query for notifications/live client state |
| API | **Python + Flask 3 REST API** (`backend/`), versioned `/api/v1` |
| Database | **PostgreSQL** + SQLAlchemy 2 + **Alembic migrations** (no SQLite/MySQL fallback) |
| Auth | Server-side sessions (hashed tokens in PostgreSQL), HttpOnly `rt_session` cookie, CSRF double-submit + server-bound token, Argon2id password hashing, RBAC, rate limiting |
| Maps | Leaflet + OpenStreetMap tiles, client-only rendering |
| Routing | OSRM table/route calls when reachable; deterministic labelled estimate fallback |
| Matching | Rule-based feasibility + pickup/delivery insertion heuristic in Python |
| Tests | Pytest (27 tests) + Vitest (5 tests) + Next.js production build/typecheck/lint |
| Local setup | Docker Compose, `.env.example`, Alembic migration, deterministic seed script |

The browser always calls same-origin `/api/v1/*`; Next.js rewrites that to Flask (`FLASK_API_URL`, server-only). Flask remains the authority for auth, permissions, matching, writes and data.

---

## 2. What is implemented

### Customer (9 views)
Landing, auth, dashboard, guided **Return a product** and **Send a parcel** forms, searchable request list, request tracking with parcel-level timeline and map context, history, profile/settings.

Customers can:
- create requests with a real pickup, distinct authorised return destination or recipient destination, window, deadline and parcel attributes;
- see only their own requests and their own parcel events;
- cancel while the request is still pending or inside a *proposed* (not yet partner-accepted) batch;
- report delivery issues without silently altering execution status.

### Delivery partner (7 views)
Dashboard/next stop, available/offered batches, batch detail, route execution, parcel status management, completed work/history, vehicle & profile.

Partners can:
- maintain vehicle type, weight/volume capacity, fragile/restricted capability, service areas, availability and operating hours;
- see only offers addressed to them plus proposals their verified profile could serve;
- accept or decline with an audited reason;
- start an accepted route and update **each parcel independently** through legal transitions;
- report failed handovers (creates an issue, requires a reason).

### Administrator (8 views)
Operations dashboard, customers, partners, request queue with detail, batch management + matching console, route monitor, issue queue, analytics/estimated sustainability.

Admins can:
- run a matching preview over real pending requests with configurable thresholds;
- inspect feasible groups, reasons for inclusion and machine-readable near-miss reasons;
- commit a proposal atomically (feasibility is recomputed; concurrency is locked);
- offer a verified eligible partner, reassign with a mandatory reason, cancel and release safely;
- verify/reject partners, disable customer accounts, resolve issues;
- inspect operational KPIs and an estimate-only sustainability report with factors and methodology.

The 24 routes are exactly those in `skill.md` (plus branded `not-found`, `error`, `forbidden` and loading states).

---

## 3. Matching engine (core)

Implementation: `backend/app/services/matching.py`.

For every candidate group the engine checks:

1. **Locations exist** and every request keeps its own destination identity.
2. **Pickup windows** are hard constraints — the schedule plans no lateness; waiting is allowed.
3. **Precedence** — a parcel's pickup index must be before its drop-off index.
4. **Deadlines** — simulated arrival at each drop-off must beat the request deadline.
5. **Capacity after every stop** — weight and volume are increased at pickups and released at drop-offs; the peak must fit the partner/reference vehicle.
6. **Handling** — fragile/restricted capability; restricted items cannot share a batch (dedicated vehicle semantics).
7. **Partner eligibility** — verified, available, operating area, handling, capacity.
8. **Pickup radius and per-request detour** — configurable coarse prefilter and maximum extra distance.
9. **Positive benefit** — the shared distance must beat the sum of direct pickup→destination trips by at least `min_savings_pct`; zero/negative savings are rejected.
10. **One active reservation** — a PostgreSQL partial unique index on `batch_requests(request_id) WHERE released_at IS NULL` prevents double booking, even concurrently.

The scheduler inserts each request's pickup/drop-off pair into every legal position of the current ordered stop list, evaluates hard constraints, and selects the lowest-distance feasible insertion. Groups are built greedily over pending requests (up to the configured cap) and each accepted group is re-solved independently before it is proposed.

Every proposal stores: ordered stops with planned arrival/departure, leg distances/durations, load after each stop, baseline and shared distance, source of distance, geometry/source, explanation reasons, assumptions, detour and vehicle metadata. A `matching_runs` row stores the whole preview result for audit.

Rejection codes include `window_conflict`, `deadline_missed`, `capacity_exceeded`, `handling_incompatible`, `restricted_exclusive`, `pickup_radius`, `service_area`, `insufficient_savings`, `already_reserved`, `not_pending`, `no_compatible_group`.

### Distance and environmental honesty

- `ROUTING_PROVIDER=auto` tries OSRM with a short timeout. On success, the matrix and geometry are labelled **OSRM road routing**.
- On failure, distance = haversine × configurable road factor; duration = distance / configurable speed. Labels literally say **estimated / not road navigation**; map connectors are dashed and captioned **illustrative**.
- The separate-trip baseline is one direct pickup→destination trip per request on the *same* distance basis; partner repositioning is excluded from both sides and this is disclosed.
- Fuel and CO₂e use configurable factors (`SUSTAINABILITY_FUEL_L_PER_KM`, `SUSTAINABILITY_KG_CO2E_PER_LITRE`). Reports never call them measured and clamp negative deltas to zero benefit.
- No live GPS, courier telemetry or invented vehicle positions are rendered.

---

## 4. Demo scenario (fictional)

Seeded by `backend/app/services/seed.py`; all names, addresses and phone numbers are fictional. Area coordinates are approximate demo points.

| Request | Customer | Service | Route | Purpose |
|---|---|---|---|---|
| `RTN-REQ-1001` | Rahul Basu | Return (shoes) | Barasat → Authorised Returns Hub — New Town | Feasible group member |
| `RTN-REQ-1002` | Priya Sen | Parcel (book) | Barasat → Salt Lake recipient | Feasible group member with a different destination |
| `RTN-REQ-1003` | Amit Roy | Return (headphones, fragile) | Barasat → Authorised Returns Hub — Salt Lake | Third distinct destination; fragile handling |
| `RTN-REQ-1004` | Sneha Mitra | Return (55 kg desk) | Barasat → Barasat hub | **Capacity counterexample** |
| `RTN-REQ-1005` | Vikram Nair | Parcel (documents) | Barasat → Dum Dum | **Deadline conflict counterexample** |
| `RTN-REQ-1006` | Farhan Ali | Parcel (restricted battery) | Barasat → Salt Lake | **Handling/restricted counterexample** |
| `RTN-REQ-1007/1008` | Neha / Arjun | Mixed | New Town + Salt Lake → hub/Birati | Completed history batch for analytics |

Seed also includes one verified van partner, one pending partner, one completed batch with parcel tracking events, two issues (one open) and audit rows.

### Demo credentials (development only — fictional accounts)

All seeded accounts use password **`ReTurn#2026`**.

| Role | Email |
|---|---|
| Administrator | `admin@return.demo` |
| Verified partner | `partner@return.demo` |
| Pending partner | `partner2@return.demo` |
| Customers | `rahul@return.demo`, `priya@return.demo`, `amit@return.demo`, and counterexample customers (`sneha@`, `vikram@`, `farhan@`, `neha@`, `arjun@return.demo`) |

> These accounts are for the local demonstration only. Never enable or reuse demo credentials in a production deployment.

### Judge walkthrough

1. Sign in as `admin@return.demo`.
2. Open **Batches → Find compatible requests**. Inspect the feasible group (returns + parcel, three different destinations), load profile, distance source, savings and rejection reasons for the capacity/deadline/restricted counterexamples.
3. Create the proposed batch (optionally offer it to the verified partner in the same run).
4. Sign in as `partner@return.demo`; accept the offer and **Start route**.
5. Open **Parcels** and advance each parcel independently: arrived → picked up → in transit → delivered. Try an illegal transition (new batch) to see the 409 guard.
6. Sign in as `rahul@return.demo` (or the other customers) to see only that customer's parcel timeline and shared-batch stops; the other customers' details are not exposed.
7. Back as admin, open **Analytics** for estimated distance/fuel/CO₂e totals, factors, methodology and the ledger. All figures are labelled estimates.

You can also create a fresh return/parcel as any customer; the default windows are generated 90–180 minutes ahead so the demonstration remains feasible. The seed resets relative windows when re-run.

---

## 5. Quick start

### Option A — Docker Compose (recommended)

```bash
cp .env.example .env          # optional; change FLASK_SECRET_KEY for anything shared
docker compose up --build
```

- Frontend: http://localhost:3000
- API health: http://localhost:5000/api/v1/health
- PostgreSQL: `localhost:5433` (`return` / `return_dev_pw` / `return_dev`)

The backend container runs `flask db upgrade` on start. With `SEED_DEMO_DATA=true` (compose default) it also reseeds the fictional demo scenario — **this is destructive** and intended for demo environments only.

### Option B — Local processes

Prerequisites: Python 3.11+, Node 20+, PostgreSQL 16+.

```bash
# 1. Database (adjust to your PostgreSQL install)
createdb -h 127.0.0.1 -p 5432 -U postgres return_dev
# Create a role/password and set DATABASE_URL accordingly, or use the example env.

# 2. Backend
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env            # edit DATABASE_URL if your port differs
flask --app wsgi db upgrade
python manage.py seed
flask --app wsgi run --port 5000      # or: python wsgi.py

# 3. Frontend (another terminal)
cd frontend
npm install
npm run dev                           # http://localhost:3000
```

For the Windows development environment used to build this project, PostgreSQL was initialised as a project-local cluster on port **5433** (because Docker Desktop's daemon was not running):

```bash
PGBIN="/c/Program Files/PostgreSQL/18/bin"
"$PGBIN/initdb.exe" -D backend/.pgdata -U postgres -A trust
"$PGBIN/pg_ctl.exe" -D backend/.pgdata -l backend/.pglog -o "-p 5433" start
"$PGBIN/psql.exe" -h 127.0.0.1 -p 5433 -U postgres -d postgres \
  -c "CREATE ROLE return LOGIN PASSWORD 'return_dev_pw' CREATEDB;" \
  -c "CREATE DATABASE return_dev OWNER return;" \
  -c "CREATE DATABASE return_test OWNER return;"
```

`backend/.pgdata` is git-ignored. The documented defaults in `.env.example` point at port 5433.

### Environment

Copy `.env.example` to `.env` (loaded by Flask). Copy `frontend/.env.example` to `frontend/.env.local` if you need to override the proxy target.

Never prefix the Flask URL, database URL or Flask secret with `NEXT_PUBLIC_`; those remain server-only.

---

## 6. Commands

| Task | Command |
|---|---|
| Backend tests | `cd backend && .venv/Scripts/python -m pytest tests -q` (Linux/macOS: `.venv/bin/python`) |
| Apply migrations | `cd backend && flask --app wsgi db upgrade` |
| Check migration drift | `cd backend && flask --app wsgi db check` |
| Seed / reset demo data | `cd backend && python manage.py seed` |
| Seed row counts | `cd backend && python manage.py check` |
| Run API | `cd backend && flask --app wsgi run --port 5000` |
| Frontend dev | `cd frontend && npm run dev` |
| Typecheck | `cd frontend && npm run typecheck` |
| Lint | `cd frontend && npm run lint` |
| Frontend unit tests | `cd frontend && npm test` |
| Production build | `cd frontend && npm run build` |
| Production server | `cd frontend && npm start` |

### Verification actually run in this build

- `pytest tests -q` → **27 passed** (PostgreSQL `return_test`).
- `vitest run` → **5 passed**.
- `tsc --noEmit` → **0 errors**.
- `next lint` → **0 errors**, two advisory `exhaustive-deps` warnings resolved in follow-up.
- `next build` → **successful production build**.
- `flask db check` → **No new upgrade operations detected**.
- Manual end-to-end smoke test through the Next same-origin proxy on PostgreSQL: CSRF bootstrap → admin login → `/auth/me` → live-OSRM matching preview (3 requests, 3 distinct destinations, 44.6% estimated saving) → commit to the verified partner → partner accept → start route → `pickup_arrived`/`picked_up`/`in_transit`/`delivered` for every parcel → batch completed; an illegal post-completion event returned **409**; the customer's payload contained no other customer identities; authenticated landing/auth/role pages returned 200.
- Docker Compose files were authored but **not executed** in this environment because the Docker daemon was unavailable; the same stack was verified locally with PostgreSQL 18 on port 5433, Flask and the built Next.js server.

No automated browser E2E suite (Playwright) is included; UI interactions were verified by typecheck/build and API flow tests rather than exhaustive browser automation.

---

## 7. Security model

- **Passwords:** Argon2id (`argon2-cffi`), no plaintext logging.
- **Sessions:** random 32-byte token, only SHA-256 hash stored in PostgreSQL; expiry, revocation, user-agent/IP metadata; HttpOnly `rt_session`, `SameSite=Lax`, `Secure` configurable for HTTPS.
- **CSRF:** every mutating `/api/v1` request requires `X-CSRF-Token` matching a first-party cookie; for authenticated requests it must also equal the token bound to the server-side session. `GET /api/v1/auth/csrf` bootstraps the cookie.
- **Authorization:** every read/write is scoped server-side. Customers read only their own requests; partners read only assigned/eligible batches; admin endpoints use role decorators. Hiding a button is never the boundary.
- **Privacy:** customer contact data is returned only to the customer, assigned partner after acceptance, or administrators. Batch serialization for customers never includes other customers' requests.
- **Rate limiting:** in-process sliding window on login, registration, matching and parcel updates. It is single-process by design; a multi-instance deployment should use Redis or an API gateway.
- **Database integrity:** FK constraints, indexes, transactions and row locks; partial unique index prevents a request from being in two active batches. Commit revalidates everything and returns `409` on conflict.
- **No secrets in the repository:** only `.env.example` values, explicitly development-only.

Known limitations: no email delivery (in-app notifications only), no MFA/email verification, no payment integration, no asset uploads, in-memory rate limiting, and demo accounts remain available while seeding is enabled.

---

## 8. Status model

- **Request:** `pending_matching → batched → assigned → in_progress → completed`, plus controlled `cancelled` and `failed`.
- **Batch:** `proposed → offered → accepted → in_progress → completed`, plus `declined`/`cancelled`.
- **Parcel:** `pending → assigned → partner_accepted → pickup_arrived → picked_up → in_transit → delivered`, with `failed`.

Transitions are validated server-side. `delivered` is impossible before pickup. A failed parcel creates an issue and keeps its tracking history. A batch is completed only when every parcel on it is terminal. Cancelling a proposal releases all reservations; cancellation is blocked once a partner is engaged.

---

## 9. Repository layout

```text
/
├── agent.md, skill.md, design.md, ReTurn_MASTER_PROMPT.md
├── README.md
├── .env.example
├── docker-compose.yml
├── backend/
│   ├── app/                 # factory, models, security, serializers, APIs, services
│   │   ├── api/             # auth, requests, matching, batches, parcels, partners, …
│   │   ├── services/        # matching, routing, dispatch, analytics, seed
│   │   └── ...
│   ├── migrations/          # Alembic (PostgreSQL)
│   ├── tests/               # pytest suite
│   ├── manage.py            # seed/check
│   ├── wsgi.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/app/             # 24 App Router views + role layouts/errors/loading
│   ├── src/components/      # design system, forms, maps, dispatch controls
│   ├── src/lib/             # typed API client, server fetch, types, formatting
│   ├── Dockerfile
│   └── ...
└── docs/
    ├── ARCHITECTURE.md
    └── ASSUMPTIONS.md
```

---

## 10. Explicit limitations and future scope

- OSRM public service may be rate-limited or unreachable; the app remains functional with labelled estimates and never presents them as road navigation.
- The optimizer is a deterministic insertion heuristic, not an exact solver or ML model. It is suitable for small demo sets (2–4 requests per batch).
- No real courier/e-commerce integrations, payments, live GPS telemetry, driver mobile app, multi-city tenancy or measured emissions.
- Maps require browser network access for OpenStreetMap tiles; the map degrades to a labelled placeholder message when coordinates are absent, and route data remains usable.
- Email notifications, MFA, partner document uploads and production-grade distributed rate limiting are future work.
- Production deployment must set a strong `FLASK_SECRET_KEY`, HTTPS + `SESSION_COOKIE_SECURE=true`, disable demo seeding, and remove seeded accounts.

Map data © OpenStreetMap contributors. Routing by OSRM when available.
