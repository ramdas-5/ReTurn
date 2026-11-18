# ReTurn architecture (v2)

## Runtime topology

```text
Browser
  │ same-origin fetch; HttpOnly rt_session + rt_csrf cookies
  ▼
Next.js 15 App Router
  ├─ server layouts call requireUser(role) and forward cookies to Flask
  └─ /api/v1/* rewrite (FLASK_API_URL, server-only)
        │
        ▼
Flask 3 /api/v1
  ├─ auth, RBAC, service-area scoping, CSRF, rate limits
  ├─ orders, returns, availability and private media
  ├─ driver duty, route execution and proof capture
  ├─ manager dispatch, batches, route-aware matching
  ├─ admin accounts, fleet, areas, configuration, audit, analytics
  └─ SQLAlchemy 2 + Alembic
        │
        ▼
PostgreSQL 16+
```

Leaflet is imported only in a client component. Server components never touch `window`.

## Frontend structure

```text
src/app/
  auth/            login, register, forgot, reset, activate
  consumer/        dashboard, orders, parcel/return creation, tracking, support, settings
  driver/          dashboard, assignments, batches, duty, vehicle, issues, notifications
  manager/         dashboard, order queue, matching, batches, drivers, live, proofs, issues, reports
  admin/           dashboard, analytics, operations, orders, batches, accounts, fleet, areas, config, audit, settings
src/components/    shell, nav, status, timeline, maps, order form, role action panels
src/lib/           API client, server cookie fetch, types, format, roles, design-tokens
```

Role layouts are server components using `requireUser(role)`. This is a navigation guard; Flask enforces authorization for every endpoint.

Visual and accessibility tokens are declared once in `src/app/globals.css` and exposed to Tailwind in `tailwind.config.ts`. The captured values from `DESIGN.md` are applied verbatim: `#ffffff` page surface, `#f5f5f5` secondary surface, `#000000` inverse surface, `#615e50` raised surface, `#201f1a`/`#413f32`/`#6d6c64` text, the `#c7d2ac` brand sage, Saans at 16px/24px (Inter fallback), the 12–48px type scale, the 4.03–16.13px spacing scale, 8/16/full radii, and 150/250 ms motion. Page chrome uses `surface.muted`; hero, sidebar and impact blocks use `surface.base` and re-declare their tokens through `.on-dark`; `.surface-light` restores the light tokens for overlays nested inside dark blocks. `src/lib/design-tokens.ts` holds the only raw palette values in TypeScript, because Recharts and Leaflet cannot resolve CSS variables in SVG attributes.

## Backend modules

| Module | Responsibility |
|---|---|
| `app/__init__.py` | factory, blueprint registration, proxy and security headers |
| `app/domain.py` | roles, statuses, transitions, permission catalog, labels, rejection codes |
| `app/models.py` | full schema: accounts, profiles, areas, vehicles, duty, orders, batches, routes, proofs, issues, settings, audit |
| `app/security.py` | Argon2id, sessions, CSRF, role/permission decorators, rate limits |
| `app/access.py` | order/batch visibility, service-area and contact boundaries |
| `app/serializers.py` | response contracts for every role |
| `app/api/auth.py` | registration, login, logout, password, reset, activation |
| `app/api/accounts.py` | self profile, addresses, business profile, staff provisioning, verification |
| `app/api/orders.py` | order intake, availability, tracking, cancellation, images |
| `app/api/returns.py` | consumer return creation, list and detail |
| `app/api/media.py` | signed private media access |
| `app/api/consumer.py` | consumer dashboard summary |
| `app/api/driver.py` | duty, location, assignments, pickup/delivery proof, exceptions, batches |
| `app/api/manager.py` | review, assignment, batches, route matching, proofs, exceptions |
| `app/api/admin.py` | global reporting, accounts, fleet, areas, matching config, settings, audit |
| `app/api/issues.py` | consumer/driver reports and manager/admin resolution |
| `app/api/notifications.py` | in-app notification feed |
| `app/api/health.py` | database-backed health check |
| `app/services/orders.py` | create order, status transitions, history |
| `app/services/dispatch.py` | eligibility, assignment, batch creation, route rebuild, capacity snapshots |
| `app/services/route_planner.py` | route planning, insertion, stored config overrides |
| `app/services/matching.py` | active-route suggestion engine and decisions |
| `app/services/routing.py` | OSRM and labelled fallback |
| `app/services/proofs.py` | capture validation (time, accuracy, distance) |
| `app/services/storage.py` | private local/S3 media, signed URLs |
| `app/services/seed.py` | fictional demo scenario |
| `app/services/analytics.py` | global counts and modelled sustainability estimates |

## Data model (principal tables)

```text
users ──1:1── consumer_profiles / driver_profiles / manager_profiles
  ├── user_sessions, one_time_tokens, notifications, audit_logs
  ├── saved_addresses
  └── orders
        ├── pickup_addresses, delivery_addresses, contacts, parcel_details, return_requests
        ├── order_status_history
        ├── parcel_images ── media_assets
        ├── driver_assignments
        ├── proof_media ── media_assets
        ├── pickup_proofs, delivery_proofs
        └── delivery_exceptions, issue_reports

service_areas ── manager_service_areas, driver_service_areas
driver_profiles ── vehicles ── vehicle_capacity_profiles
driver_profiles ── driver_duty_sessions ── driver_location_events

delivery_batches ── batch_orders
  ├── route_plans ── route_stops
  ├── matching_suggestions
  └── driver_assignments

admin_settings, permissions, user_permissions
```

Key database guarantees:

- unique email and session-token hash;
- one active assignment per order, enforced in dispatch logic and constrained writes;
- one active batch membership per order (`batch_orders.removed_at IS NULL`);
- unique driver duty session per driver (`ended_at IS NULL`);
- foreign keys and indexes on status, area, duty, route and audit lookups.

## Dispatch lifecycle

```text
submitted → pending_review → awaiting_assignment → assigned
          → pickup_scheduled → pickup_arrived → picked_up
          → in_transit → out_for_delivery → delivery_proof_pending?
          → delivered / returned | failed | cancelled
```

Transitions are validated in `domain.can_transition` and written only through `record_status`, which appends `order_status_history`. Delivery completion additionally requires a validated proof when configured.

## Matching flow

```text
manager scans approved orders
  └─ for each driver visible to the manager:
       eligibility (active, verified, duty live, area, vehicle, capacity)
       active route must exist
       pickup distance to route corridor ≤ max_pickup_radius_km
       compute best pickup/delivery insertion into remaining stops
       check precedence, windows, deadline, load after each stop, detour
       persist feasible suggestion with score, reasons, blockers, capacity snapshot
manager approves → engine revalidates → order assigned / active route extended
manager rejects → suggestion closed with reason
```

Administrator overrides in `admin_settings` key `matching.defaults` are merged over environment defaults by `route_planner.config()`.

## Authentication and CSRF

```text
GET /auth/csrf                      → rt_csrf cookie
POST /auth/login + X-CSRF-Token     → session row + HttpOnly rt_session + rotated rt_csrf
Mutating request                    → header == cookie == session.csrf_token
```

Sessions are server-side. Only the SHA-256 hash of the random token is stored. Server layouts forward the cookie header to Flask.

## Media

- Uploads are validated by MIME type and magic bytes, with a size limit.
- Files are private: never served from a static path.
- `GET /api/v1/media/<id>?expires=…&signature=…` verifies an HMAC signature and authorization scope.
- Driver proof images include capture time, coordinates, accuracy and distance from the stop.
- Local storage is the development fallback; S3 is supported for durable deployment.

## Notifications and audit

Notifications are stored per user and polled by the client. Dispatch, proof review, exceptions, account status, verification, matching configuration and settings changes create append-only audit rows with actor, summary, reason and metadata.
