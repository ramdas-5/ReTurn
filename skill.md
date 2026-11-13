# ReTurn — SKILL.md

> Practical domain workflow and engineering playbook for an AI agent building ReTurn.
> Read after `agent.md`; apply visual guidance from `design.md`.

## 1. Product mental model

ReTurn brings together **return pickups** and **ordinary outgoing parcels** that can share one partner's journey **without violating** each parcel's destination, availability, deadlines, vehicle capacity or handling needs. It is a **coordination and constrained-route-planning app**, not a fleet-owning courier business or a magic “AI” dispatcher.

### End-to-end happy path

1. Customer signs in and chooses `Return a Product` or `Send a Parcel`.
2. Customer enters pickup, authorized return destination or recipient destination, time window, parcel attributes and optional deadline.
3. Server validates, persists request and parcel; request begins at `pending_matching`.
4. Admin invokes matching (or a configurable job does so). Engine proposes groups **only after feasibility and savings tests**.
5. Admin reviews route, constraints, rejection explanations, stops and comparable estimated distances.
6. Admin offers the batch to a verified, available, capacity-compatible partner (manual dispatch works for MVP).
7. Partner accepts; navigation/route stops display; parcel-level pickup and delivery events are recorded.
8. Customers see their own event timeline; admin sees whole batch; partner sees assigned tasks.
9. Reports compare **estimated combined** travel with a defined **estimated separate-trip baseline** and disclose assumptions.

## 2. Essential business objects

| Object | Required fields / rules |
|---|---|
| `User` | id, email unique, name, password hash, role, created_at, disabled_at |
| `PartnerProfile` | user_id, verification state, service area, vehicle type, max weight/volume or accepted size classes, availability |
| `Location` | structured address, lat/lon if resolved, optional geocoding/source quality and time zone |
| `DeliveryRequest` | id, customer_id, type (`return` / `parcel`), pickup, destination, pickup window start/end, delivery deadline, status, timestamps |
| `Parcel` | id, request_id, description, size/weight, fragile/handling flags, tracking number, current status |
| `ReturnDetail` | request_id, authorized hub/destination, optional return reference; never substitute an arbitrary hub |
| `RecipientDetail` | request_id, recipient name/contact accessible only when operationally necessary |
| `DeliveryBatch` | id, status, proposed route estimate, baseline estimate, partner assignment, source/method of estimate |
| `BatchStop` | id, batch_id, request_id, kind (`pickup`/`dropoff`), sequence, location, estimated arrival, service minutes |
| `TrackingEvent` | id, parcel_id, event type, timestamp, actor, notes; append-only history |
| `Notification` | id, user_id, type, body, read_at |
| `IssueReport` | id, request_id, reporter_id, issue type, description, severity, resolution status |
| `AuditEvent` | actor, action, entity, old/new summary, reason, timestamp; particularly for admin actions |

**Database constraints**: preserve referential integrity; each active request has at most one active batch assignment; create batch and attach requests in one transaction; two distinct stop rows per request at minimum. Index pending status, pickup window, owner and batch references.

## 3. Matching engine: practical procedure

### Input

A set of eligible pending requests with valid coordinates, parcel requirements and locations; active eligible partners or available vehicle profiles; tuning parameters such as max pickup radius, maximum additional detour, minimum estimated savings, allowed lateness (= 0 for hard windows), average service time per stop, candidate batch cap and time budget.

Make these parameters configurable and visible in the admin settings/analysis documentation; **do not present example thresholds as universally optimal**.

### Phase A — hard compatibility filters

For each candidate pair/group:

- The two pickup neighborhoods are potentially serviceable by a partner/route (nearby is a coarse prefilter, not final approval).
- Time windows allow a schedule, including travel and stop service times.
- All return destinations are exactly those authorized for the respective return.
- All regular parcel destinations remain the recipients' own destinations.
- All parcels fit the vehicle **at each route segment**, not merely as a static sum; check weight and volume/size plus fragile/restricted compatibility.
- Delivery deadlines are feasible; pickup always precedes that parcel's delivery.
- Partner is verified/eligible, available, and within a configured operating area.
- Any request already actively reserved/batched is excluded.

If no partner is available, the engine may generate a clearly marked **unassigned feasible proposal** using a configured vehicle profile; it must not claim a real partner is assigned.

### Phase B — routing and route simulation

Use OSRM road distances/durations when reachable. Consider a pickup-and-delivery precedence-constrained insertion heuristic for the MVP:

```python
for pending_request in prioritized_pending_requests:
    feasible = []
    for candidate_batch in eligible_batches_and_new_batch_candidates:
        for pickup_position in allowed_insertions(candidate_batch):
            for dropoff_position in positions_after_pickup(pickup_position):
                tentative = insert_pair(candidate_batch, pending_request,
                                        pickup_position, dropoff_position)
                if every_hard_constraint_passes(tentative):
                    feasible.append(tentative)
    pick best plan by savings / time / detour criteria, or leave unmatched

commit selected batches with a transaction and uniqueness/locking checks
```

Compute travel time between consecutive stops, arrival time, waiting if an early pickup, service time, and parcel load after each pickup/drop-off. Honor precedence. Evaluate 2–4 request groups first; tune for small student/hackathon demo sets. An exact solver is not required.

### Phase C — benefit and decision

For the same set of requests, estimate independent journeys under a **stated, consistent** baseline (e.g., sum of separately dispatched pickup→drop-off route distances; if partner repositioning is omitted from both estimates, say so). Define:

```text
estimated_distance_saved_km = max(0, baseline_km - combined_km)
raw_distance_delta_km       = baseline_km - combined_km
estimated_savings_percent   = 100 * raw_distance_delta_km / baseline_km
estimated_fuel_saved_l      = estimated_distance_saved_km * fuel_l_per_km
estimated_CO2e_avoided_kg  = estimated_fuel_saved_l * kg_CO2e_per_litre
```

Require positive raw savings and configurable minimum operational benefit **before** creating a recommended batch. If comparing two different measurement methods, block the comparison or clearly flag it as non-comparable. Never treat haversine as road kilometers without labeling the estimate. Do not claim actual fuel/emissions savings.

### Phase D — explainability

Every proposed batch should display:
- which requests are included;
- why they were compatible;
- pickup/drop-off order and expected time windows;
- vehicle load profile / max loading point;
- baseline distance and shared-route distance, with measurement source;
- calculated savings and assumptions;
- warning/rejection reasons for near misses (`window_conflict`, `capacity_exceeded`, `deadline_missed`, `handling_incompatible`, `destination_detour`, `no_eligible_partner`, `insufficient_savings`, etc.).

### Reliability fallback

When OSRM is unavailable, use a deterministic local estimation strategy only for **illustrative/demo route scoring**, label the output `Estimated / demo route`, and disclose limitations. The map may show straight-line connector paths labeled **approximate**, but do not show them as road navigation. The actual route-stop ordering and precedence rules still work without external routing.

## 4. Dispatch, execution and state machines

### Admin dispatcher

`proposed -> offered -> accepted -> in_progress -> completed`

- Proposal reserves requests atomically; do not allow multiple active proposals to claim one request.
- An offer can be declined; a declined offer must release or re-offer safely.
- Assignment requires a verified and operationally eligible partner.
- Reassignment must revoke the former assignment, update authorization and create an audit event.
- An accepted batch cannot be casually cancelled without handling in-flight parcels and customer notification.

### Delivery execution

For every request/parcel within a batch:
1. Partner may mark `pickup_arrived` at the pickup stop.
2. Partner confirms pickup: `picked_up`, with timestamp and optional evidence/reference.
3. Partner moves parcel `in_transit` after pickup.
4. Partner confirms `delivered` only after pickup and only for their active batch.
5. Partner reports failed attempts or problems with reasons, generating an issue and notification.

Do not infer a parcel's delivery state from its batch mates. A batch is completed only when every parcel has a valid terminal resolution (delivered or explicitly resolved failed/returned, as modeled).

### Customer cancellation

Allow before assignment/acceptance according to an explicit policy; if already reserved in a proposed batch, transactionally remove the request and recompute feasibility (or dissolve the proposal). Never delete tracking history to “reset” the parcel.

## 5. Screens / routes (24 brief-defined views)

The initial project brief specifies **9 customer-facing, 7 partner, and 8 admin views**. Keep them all, but shared auth/components may be implemented once.

### Customer-facing (9)

| Route | View and functional goal |
|---|---|
| `/` | Landing: benefit, services, process, CTA, trust/estimate disclaimers |
| `/auth` | Registration and login (role-aware; partner sign-up is pending verification) |
| `/customer` | Dashboard: active requests, nearest action, compact stats |
| `/customer/returns/new` | Create return: authorized return hub, reference, pickup/time/parcel form |
| `/customer/parcels/new` | Create parcel: recipient/destination, pickup/time/parcel form |
| `/customer/requests` | My Requests: searchable/filterable list, status and next step |
| `/customer/requests/:id` | Details/tracking: parcel events, assigned partner (when permitted), journey |
| `/customer/history` | Request history with completed/cancelled items |
| `/customer/settings` | Profile/settings and notification preferences |

### Delivery partner (7)

| Route | View and functional goal |
|---|---|
| `/partner` | Partner dashboard: active batch, shifts, completed counts |
| `/partner/batches` | Available or offered batches: accept/decline when eligible |
| `/partner/batches/:id` | Batch details: parcels, stops, time windows, eligibility |
| `/partner/batches/:id/route` | Route map and ordered pickup/drop-off itinerary |
| `/partner/batches/:id/parcels` | Parcel status management with valid transitions |
| `/partner/history` | Completed deliveries/batches and exceptions |
| `/partner/profile` | Vehicle, capacity, operating area, availability, verification status |

### Admin (8)

| Route | View and functional goal |
|---|---|
| `/admin` | Operations dashboard: KPIs, live states, alerts, matching CTA |
| `/admin/customers` | Customer management, safe account detail actions |
| `/admin/partners` | Verify and manage partners; availability and capacity |
| `/admin/requests` | All requests: filter, inspect, action, unmatched reasons |
| `/admin/batches` | Run matching, review proposals, offer/reassign/cancel safely |
| `/admin/routes` | Route monitoring, map/stop/status overview |
| `/admin/issues` | Queue, severity, resolution audit trail |
| `/admin/analytics` | Operations + estimated sustainability dashboard and methodology |

Create shared layouts, error/not-found/forbidden states and reusable dialogs without inflating the advertised count.

**Next.js implementation requirement:** Build these paths with the **App Router**, not React Router. For dynamic routes, use directories such as `src/app/customer/requests/[id]/page.tsx` and `src/app/partner/batches/[id]/route/page.tsx`. Create `layout.tsx` for role-specific shells; handle `loading.tsx`, `error.tsx` and `not-found.tsx` as appropriate. Use Server Components for safe initial page composition and Client Components (`'use client'`) for interactive forms, route maps, live state, dialogs and client-side fetching. Do not use `getServerSideProps` or legacy Pages Router patterns. Private operational data must use per-user fetching with no shared/public caching; Flask REST API and PostgreSQL remain the business/data source of truth.

## 6. API contract (recommended REST structure)

Implement versioned Flask endpoints (`/api/v1`) and consistent envelopes, pagination, structured errors and authentication. Sample shapes below are contracts for implementation, not endpoints already available. Next.js frontend should call these over its same-origin `/api/v1/*` rewrite to the Flask service (or a clearly justified secure server-only bridge). Do not put PostgreSQL credentials in the browser or duplicate core Flask business logic inside Next.js route handlers.

| Method | Endpoint | Allowed action |
|---|---|---|
| `POST` | `/auth/register` | register customer or pending partner |
| `POST` | `/auth/login` | sign in / secure session |
| `POST` | `/auth/logout` | revoke session |
| `GET` | `/auth/me` | identity/role/capabilities |
| `GET, POST` | `/requests` | own requests or admin listing; create validated requests |
| `GET` | `/requests/{id}` | role/ownership-filtered details |
| `POST` | `/requests/{id}/cancel` | authorized cancellation |
| `GET` | `/requests/{id}/tracking` | own/assigned/admin parcel events |
| `POST` | `/matching/preview` | admin feasibility preview + explanations |
| `POST` | `/matching/commit` | admin atomic proposal creation; recompute before commit |
| `GET` | `/batches` | role-filtered batch list |
| `GET` | `/batches/{id}` | authorized batch details/stops |
| `POST` | `/batches/{id}/offer` | admin offers to eligible partner |
| `POST` | `/batches/{id}/decision` | partner accepts/declines |
| `POST` | `/batches/{id}/reassign` | audited admin reassign |
| `POST` | `/parcels/{id}/events` | partner/admin validated event update |
| `GET, POST` | `/issues` | authorized list/report creation |
| `PATCH` | `/issues/{id}` | admin resolution |
| `GET` | `/notifications` | current user's notifications |
| `PATCH` | `/notifications/{id}` | mark own notification read |
| `GET` | `/analytics/summary` | admin dashboard metric aggregates |
| `GET` | `/analytics/sustainability` | estimates + factors + methodology |
| `GET, PATCH` | `/partners/me` | own partner profile |
| `PATCH` | `/partners/{id}/verify` | admin verification with audit |

Use a single canonical request creation payload with `type` plus service-specific fields. Return field validation errors, conflict (`409`) when a concurrent actor claimed a request, and correct auth statuses (`401/403`). Never trust caller-supplied `customer_id`, `partner_id` or calculated savings without checking permission/recomputing.

## 7. Implementation sequence (carry out end to end)

**Step 1 — foundation:** inspect existing repo; initialize monorepo, Flask backend factory, **PostgreSQL schema/migrations**, **Next.js App Router + TypeScript** in `frontend/`, Tailwind design tokens, file-based routes/nested layouts, same-origin API proxy, auth and RBAC.

**Step 2 — request lifecycle:** implement forms, maps/location handling, list/detail/history pages, database persistence, event history, cancellation and notifications.

**Step 3 — intelligence:** implement hard compatibility rules, route insertion, feasibility simulation, savings baseline and explanations; add deterministic regression fixtures.

**Step 4 — dispatcher:** admin request queue, preview/commit matching, batch review/assignment, partner acceptance, route display, per-parcel status updates.

**Step 5 — oversight:** admin user/partner/issue management, audit, reports and customer-facing tracking.

**Step 6 — hardening:** mobile UX, empty/error states, concurrency, authorization tests, builds, migrations and documented setup.

These are implementation dependencies, **not gates for waiting on user approval**. Complete the deliverable in the available working session; report genuine blockers.

## 8. Demo fixture / judge walkthrough

Seed **fictional** requests in the Barasat / Kolkata region:
- **Rahul** — returns shoes from Barasat to the **authorized return hub**.
- **Priya** — sends a book from a nearby pickup to its recipient in **Salt Lake**.
- **Amit** — returns headphones from a nearby pickup to its **authorized return hub**.

Use plausible **illustrative** pickup windows and capacities that make a shared batch feasible; also seed a **negative test** with a deadline conflict or an oversized parcel. The demo must show matching reasons and rejected reasons rather than assuming all three nearby requests always match. Use geographic area names, not invented real customer street addresses.

Demonstration: customer submissions → admin queue → explainable batch preview → commit and offer → partner accept → map/ordered stops → per-parcel tracking → admin estimated savings dashboard.

## 9. Quality and acceptance checklist

- [ ] `ReTurn` branding everywhere; consistent menus and breadcrumb labels.
- [ ] All 24 views exist with meaningful role-specific content.
- [ ] Two creation journeys persist real requests.
- [ ] Feasibility rejects incompatible time, capacity, handling and deadline combinations.
- [ ] Pickup-before-drop-off rule covered by tests.
- [ ] Independent tracking events and status transition protections.
- [ ] No duplicate reservation under concurrent matching.
- [ ] Partner verification, account ownership, admin RBAC and CSRF/rate limits.
- [ ] Maps and routing behave honestly when service is unavailable.
- [ ] Savings labeled estimated; assumptions visible and consistent.
- [ ] Inputs, buttons, navigation, filters and dialogs function.
- [ ] Responsive layouts, keyboard flow and accessible status presentation.
- [ ] Next.js App Router + TypeScript app, Flask API and **PostgreSQL** are used throughout; no Vite or React Router app.
- [ ] Next.js production build, seed scripts, `.env.example`, setup guide, PostgreSQL migrations and successful tests.

## 10. Out of MVP / future scope

Real-time GPS telemetry, ecommerce provider integration, courier-network integration, payment gateways, autonomous large-scale dispatch, complex ML, and multi-city commercial operations belong to **future phases**. They can be visually referenced as future features if clearly disabled/labeled, but must not displace the tested core demonstration.
