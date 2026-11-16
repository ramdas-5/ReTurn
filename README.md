# ReTurn — Reverse Delivery & Shared Logistics

**One route. Multiple deliveries. Less waste.**

ReTurn is a four-role logistics platform for **parcel delivery** and **product returns**. Consumers book orders, operations managers review and dispatch them, drivers execute routes with proof, and administrators control the platform and audit evidence. Shared routes are only created when the server proves them feasible.

The platform is honest by design:

- no public driver, manager or administrator registration;
- no delivery completion without captured proof when proof is required;
- no invented GPS positions;
- no fabricated dashboard statistics — every figure is counted from PostgreSQL rows;
- distance, fuel and CO₂ figures are labelled **modelled estimates**, never measured telemetry.

---

## 1. Stack

| Layer | Implementation |
|---|---|
| Frontend | Next.js 15 App Router, React 19, TypeScript, Tailwind CSS |
| Data fetching | TanStack Query in client components; server-side role guards and cookie forwarding |
| API | Flask 3 REST API at `/api/v1`, twelve blueprints |
| Database | PostgreSQL + SQLAlchemy 2 + Alembic |
| Auth | Server-side sessions, HttpOnly `rt_session`, CSRF double-submit + session-bound token, Argon2id, RBAC, rate limits |
| Mapping | Leaflet + OpenStreetMap, client-only |
| Charts | Recharts, client-only |
| Routing | OSRM when reachable; clearly labelled deterministic fallback otherwise |
| Media | Private local storage in development, S3 adapter available |
| Tests | Pytest (PostgreSQL) + Vitest + Next typecheck/lint/production build |

---

## 2. Roles and workflows

### Consumer (`/consumer`)
- register, sign in, reset password, activate an invited account;
- dashboard with real active orders, history and notifications;
- send a parcel or create a product return with exterior photo (or documented exception), real availability check, pickup window and deadline;
- order detail, dedicated tracking timeline, cancellation before custody, additional photos, support issues;
- saved addresses, business profile, notification preferences and password change.

### Driver (`/driver`)
- mobile-first dashboard with duty state, vehicle load and next stop;
- start/end duty, change availability, heartbeat and consent-based location updates;
- assigned orders and batches, ordered route map, navigation links;
- accept work, mark arrival, confirm pickup with photo and location, depart, go out for delivery, complete with delivery proof;
- report delivery exceptions, view history, edit vehicle details, notifications.

### Manager (`/manager`)
- operations summary scoped to service areas;
- order review (approve/reject), assignment and reassignment with server-revalidated eligibility;
- pending assignments, batch creation, batch detail with route stops, reassignment and cancellation;
- route-aware suggestion scan, approval and rejection with capacity/detour evidence;
- driver list and driver account creation, live duty/tracking board, route and progress views;
- proof verification, driver exceptions, consumer issues, operational reports.

### Administrator (`/admin`)
- global dashboard, analytics and sustainability estimates with methodology;
- global live operations and route monitoring;
- all orders and batches with dispatch controls;
- consumer, business, manager and driver administration; driver and vehicle verification; account suspension;
- service area CRUD, matching configuration, proof audit, audit logs, platform settings;
- manager and driver account provisioning with one-time activation tokens.

Every read and write is authorized by Flask. Hiding a button is never the security boundary.

---

## 3. Implemented API surface

| Area | Endpoints |
|---|---|
| Auth | `/auth/csrf`, `/register`, `/login`, `/logout`, `/me`, `/password`, `/forgot-password`, `/reset-password`, `/activate`, `/resend-activation` |
| Consumers | `/consumer/summary`, `/consumer/notification-preferences` |
| Orders | `/orders` (create/list/detail), `/orders/<id>/tracking`, `/cancel`, `/images`, `/availability` |
| Returns | `/returns` (create/list/detail), `/returns/<id>/cancel` |
| Accounts | `/users/me`, `/users/me/addresses`, `/business-profiles/me`, `/users/managers`, `/users/drivers`, `/users/<id>/status`, `/users/<id>/driver-verification` |
| Driver | `/driver/profile`, `/driver/vehicle`, `/driver/duty*`, `/driver/location`, `/driver/summary`, `/driver/assignments*`, `/driver/orders/<id>/{accept,arrived-pickup,pickup,depart,out-for-delivery,delivery-proof,exception}`, `/driver/batches*` |
| Manager | `/manager/summary`, `/manager/orders*`, `/manager/drivers*`, `/manager/batches*`, `/manager/matching/*`, `/manager/proofs*`, `/manager/exceptions*` |
| Admin | `/admin/summary`, `/admin/analytics*`, `/admin/consumers`, `/admin/businesses`, `/admin/managers`, `/admin/drivers`, `/admin/vehicles*`, `/admin/orders*`, `/admin/batches*`, `/admin/operations/live`, `/admin/proofs*`, `/admin/service-areas*`, `/admin/matching-config`, `/admin/settings*`, `/admin/audit`, `/admin/exceptions*` |
| Shared | `/health`, `/issues`, `/notifications`, `/service-areas`, `/vehicle-capacity-profiles`, `/media/<id>` (signed) |

---

## 4. Dispatch and matching rules

The matching engine (`backend/app/services/matching.py`) evaluates a new order against each driver's **active route**:

1. driver verified and active; vehicle active and verified;
2. live duty session with a fresh heartbeat;
3. driver covers the pickup service area;
4. projected parcel/weight/volume load fits the vehicle;
5. pickup lies within the configured route corridor;
6. inserting pickup **before** delivery preserves precedence;
7. simulated arrivals respect the pickup window and delivery deadline;
8. added detour and added duration are within configured limits;
9. every result stores reasons, blockers, capacity snapshot and proposed sequence.

A manager must approve a suggestion; approval re-runs the evaluation before assigning. The scan never auto-assigns.

Delivery completion is validated server-side: proof photo, capture time, accuracy, distance from the stop, duty session and signed media access. `DELIVERY_PROOF_REQUIRED=true` by default. A driver who cannot capture proof reports `proof_capture_failed`; the delivery is not marked complete.

---

## 5. Demo data

`python manage.py seed` resets the **local development database** and creates a fictional scenario:

- 5 service areas around Kolkata;
- 1 administrator, 1 manager, 2 drivers, 3 consumers;
- 6 orders: review queue, active shared route, an on-route suggestion, a delivered order with proof, and an exception;
- 1 active batch, 1 pending matching suggestion, 1 proof image, notifications and audit rows.

All demo accounts use password **`ReTurn#2026`**.

| Role | Email |
|---|---|
| Administrator | `admin@return.demo` |
| Manager | `manager@return.demo` |
| Drivers | `arjun@return.demo`, `vikram@return.demo` |
| Consumers | `priya@return.demo` (business), `rahul@return.demo`, `amit@return.demo` |

> Demo accounts and data are fictional. Never enable demo seeding on a deployment that stores real personal data.

### Suggested walkthrough

1. Sign in as the manager, open **Order queue**, approve a pending order.
2. Open **Pending assignments**, then the order, and scan active routes.
3. Approve a feasible suggestion or assign a driver directly.
4. Sign in as the assigned driver, start duty, accept the work and complete the lifecycle. Delivery proof requires a photo and location.
5. Sign in as the consumer to follow the parcel-level timeline and proof.
6. Sign in as the administrator to inspect analytics, verify a proof, tune matching, or review the audit log.

---

## 6. Local setup

Prerequisites: Python 3.11+, Node 20+, PostgreSQL 16+.

```bash
cp .env.example .env                 # development defaults; change secrets for anything shared

# Backend
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv/Scripts/activate
pip install -r requirements.txt
flask --app wsgi db upgrade
python manage.py seed
flask --app wsgi run --port 5000

# Frontend (second terminal)
cd frontend
npm install
npm run dev                          # http://localhost:3000
```

`python manage.py seed` is optional: it resets the local database and loads the fictional demo scenario. For a clean database, create the first administrator instead:

```bash
flask --app wsgi bootstrap-admin --email admin@example.com --name "Operations Admin"
```

Without `--password` (or `BOOTSTRAP_ADMIN_PASSWORD`) the command prints a generated password once. It also inserts the permission catalogue, rejection codes and vehicle capacity profiles, and refuses to create a second administrator. Sign in as that account and create service areas, managers and drivers from `/admin`.

The frontend proxies `/api/v1/*` to `FLASK_API_URL` (default `http://127.0.0.1:5000`). Server layouts call Flask through `API_INTERNAL_URL`. Neither variable may be exposed as `NEXT_PUBLIC_*`.

### PostgreSQL on this machine

The verified local environment uses a project-local PostgreSQL 18 cluster on port **5433**:

```bash
PGBIN="/c/Program Files/PostgreSQL/18/bin"
"$PGBIN/pg_ctl.exe" -D backend/.pgdata -l backend/.pglog -o "-p 5433" start
```

Databases: `return_dev` and `return_test`; role `return` / `return_dev_pw`. `backend/.pgdata` is ignored by Git.

### Docker Compose

```bash
docker compose up --build
```

- frontend `http://localhost:3000`
- API health `http://localhost:5000/api/v1/health`
- PostgreSQL `localhost:5433`

The backend entrypoint runs Alembic and seeds only when the database has no users. Media is stored in the `return_media` volume; local media is not suitable for multi-instance production.

---

## 7. Verification

Commands used for the final check:

```bash
cd backend && .venv/Scripts/python -m pytest tests -q
cd frontend && npm run typecheck && npm run lint && npm test && npm run build
```

Verified in this environment on 16 November 2026:

- **Backend:** 59 passed against PostgreSQL.
- **Bootstrap:** a fresh database migrated to head and `bootstrap-admin` created exactly one administrator; a second run was refused.
- **Frontend unit tests:** 3 passed.
- **TypeScript:** `tsc --noEmit` passed; **lint:** no warnings or errors.
- **Production build:** `next build` passed; mutating routes are server-rendered and the Recharts analytics bundles compile.
- **Seeded role smoke:** all four demo roles signed in, read their dashboards, the manager read the seeded batch detail, and the admin read the seeded proof.
- **Migrations:** a fresh PostgreSQL database upgraded to the current head (`cb7ba7082235`); `flask db check` found no model drift. A second upgrade on the development database was also clean.
- **Deployment config:** `docker compose config` validated. Container images were not built here because the local Docker daemon was unavailable; no hosted deployment has been performed.

The backend suite requires PostgreSQL; it does not fall back to SQLite. The API flow is covered by Pytest for auth/RBAC, order intake, dispatch eligibility, batch planning, matching, proof validation, admin configuration, issues and driver profile. No Playwright/browser E2E suite is included.

---

## 8. Deployment

The repository supports **Vercel (Next.js) + Render (Flask Docker) + Neon PostgreSQL**. See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for account setup, environment variables, migrations, seeding and troubleshooting.

Critical production steps:

1. Set a strong `FLASK_SECRET_KEY`.
2. Use HTTPS and `SESSION_COOKIE_SECURE=true`.
3. Set `SEED_DEMO_DATA=false` before real data is stored.
4. Create the first administrator with `flask --app wsgi bootstrap-admin`, or set `BOOTSTRAP_ADMIN_EMAIL`/`BOOTSTRAP_ADMIN_PASSWORD` so the container does it on boot, then remove the password variable.
5. Configure the Vercel URL in `CORS_ALLOWED_ORIGINS` (defence in depth).
6. Use S3 (`MEDIA_BACKEND=s3`) for proof images; Render's local filesystem is ephemeral.
7. Warm a sleeping free Render service before a demo.

`render.yaml`, `frontend/vercel.json`, Dockerfiles and `.env.example` are included.

---

## 9. Security model

- Argon2id password hashing; no plaintext credentials.
- Random session token; only a SHA-256 hash is stored. HttpOnly, SameSite=Lax, Secure-configurable cookie.
- CSRF required on every mutating `/api/v1` request, with a server-bound token for authenticated sessions.
- RBAC and service-area scoping enforced on every endpoint; consumers only read their own orders; drivers only assigned work; managers only their areas; administrators globally.
- Signed, expiring media URLs; media is never served from a public static directory.
- Audit rows for dispatch, proof review, account status, verification, settings, matching configuration and issues.
- Rate limits on login, registration, order intake, assignments, proof and configuration writes. The limiter is in-process and intended for single-instance deployments.

---

## 10. Honest limitations

- Email delivery, MFA and payment integration are not implemented. Reset/activation tokens are returned in development when `AUTH_EXPOSE_RESET_TOKENS=true`.
- The matching engine is a deterministic insertion heuristic, not machine learning or an exact solver.
- OSRM may be unavailable; fallback distances are labelled estimates and maps show illustrative connectors.
- There is no live vehicle GPS feed. Only consciously shared, on-duty location events are displayed, with stale/unavailable labels.
- Local media on a single container is ephemeral in hosted environments; use S3 for durable proof storage.
- No browser automation suite is included; UI verification is typecheck, lint, unit test and production build.
- Docker Compose configuration is supplied and syntactically validated; container image builds and hosted deployment require a Docker daemon and provider accounts, so they were not exercised here.
