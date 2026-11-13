# ReTurn — AGENT.md

> Repository-level operating instructions for the AI software-engineering agent.
> Product: **ReTurn — Smart Reverse Delivery & Shared Logistics Platform**
> Tagline: **One Route. Multiple Deliveries. Less Waste.**
> Read this file, `skill.md`, and `design.md` before editing code.

## 1. Mission

Build a **real, end-to-end, secure, responsive web application** that coordinates compatible e-commerce returns and ordinary parcel deliveries into shared delivery batches. The product does **not** operate a courier fleet or promise that all journeys can be combined; it connects customer requests with eligible delivery partners and evaluates route feasibility.

**Project name is locked: ReTurn.** This is the exact name in the source project brief. Preserve the capitalization `ReTurn` in the application name, user-visible copy, logo, repository documentation, metadata and sample material. Never rename or rebrand the product on your own. If you encounter an alternate name from earlier generated instructions, treat it as an error and restore **ReTurn**. Do not confuse the brand name with the generic service called a product return.

The primary innovation is **feasible multi-request batching + pickup-before-delivery routing**, **not** conventional individual parcel tracking.

## 2. Source of truth and precedence

1. Current explicit user instruction, including the locked **ReTurn** project name.
2. Product requirements and domain constraints in this `agent.md` and `skill.md`.
3. Visual and interaction contract in `design.md`.
4. Uploaded project explanation (`ReTurn_Detailed_Project_Explanation(3).md`) as the original product brief.
5. Established patterns in this repository, where compatible with the above.

When requirements conflict, implement the higher-priority instruction, note the resolution in the README, and do not silently remove a core workflow. The architecture and visual system below are **implementation decisions**, while the two services, three roles, feasibility checks, tracking, and sustainability-estimate caveats come from the project brief.

## 3. Non-negotiable product boundaries

### Services
- **Product Return:** pickup from the customer and delivery to that return's **authorized** return hub/destination; capture a return reference when available.
- **Send a Parcel:** pickup from the sender and delivery to the specified recipient/address.
- A shared batch may contain both types and **different destinations**; never redirect them to a common hub to simplify the route.

### Roles
- **Customer:** create, see, track, and—in permitted states—cancel their own requests; view history; report issues.
- **Delivery Partner:** manage eligibility/vehicle details, see offered batches, accept or decline, execute routes, update individual parcel statuses, report failures, view work history.
- **Administrator:** verify partners, manage requests and batches, trigger matching, make audited manual assignments or reassignments, monitor route execution, resolve issues, inspect analytics.

### Matching invariants
Do **not** batch merely because pickups are close. Check pickup windows, destinations and time windows, pickup-before-drop-off precedence, deadlines, physical vehicle capacity throughout the itinerary, service area, handling compatibility, partner availability, and a plausible operational saving. Reject infeasible groupings with user-explainable reasons. A parcel can belong to at most **one active batch** at a time.

### Data integrity and disclosures
- Keep a **parcel/request-level tracking history** separate from batch status.
- Do not fabricate live GPS, measured fuel consumption, real-time courier integrations, or measured emissions savings.
- Any simulated positions or savings must be labeled **demo**, **estimated**, or **illustrative**, as applicable.
- Sustainability numbers compare a documented separate-trip baseline to a combined-route estimate, with consistent distance assumptions, a configurable fuel factor, and a configurable CO2e factor.

## 4. Approved MVP stack

| Layer | Decision |
|---|---|
| Frontend | **Next.js (App Router) + React + TypeScript** |
| Design | Tailwind CSS + accessible headless components (e.g., shadcn/ui patterns) + Lucide icons |
| Routing/UI state | **Next.js file-system App Router**, server/client components, TanStack Query for client cache, React Hook Form + Zod |
| API | Python 3 + Flask, REST, Marshmallow/Pydantic or equivalent validation |
| Database (mandatory) | **PostgreSQL** + SQLAlchemy + Alembic migrations; no SQLite as the main database |
| Auth | Server-managed secure session cookies with CSRF protection, or an equivalently hardened approach if the repository already mandates it |
| Maps | Leaflet + OpenStreetMap map tiles |
| Road routing | OSRM when reachable; labeled deterministic estimation fallback for demo/offline use |
| Matching | Python **rule-based** feasibility and route scoring (no false AI/ML claims) |
| Tests | Pytest; Vitest/React Testing Library as applicable to Next.js; Playwright smoke tests if practical; Next.js production build and typecheck |
| Local setup | `.env.example`, Docker Compose for database/services, reproducible seed command |

**Next.js and PostgreSQL are mandatory choices.** Do not replace Next.js with Vite, plain React SPA, or React Router, and do not use SQLite/MySQL as the primary persistent store. Keep the Flask REST API and SQLAlchemy backend specified in the original blueprint; Next.js renders the UI and consumes the Flask API.

**Frontend/back-end boundary:** Prefer same-origin browser requests at `/api/v1/*` proxied by a Next.js rewrite to Flask, with the Flask URL configured via server-only environment variables for local/Docker deployments. Keep Flask the owner of auth sessions, permissions, matching, tracking and database writes. If Next.js server components or route handlers call Flask, explicitly forward only necessary user cookies/headers securely and never expose server-only secrets or customer data to the client. Use `fetch` caching intentionally: auth/private operational data must not be publicly cached or statically generated. All protected routes must be authorized by Flask; Next.js middleware/layout redirects are convenience, not the security boundary.

**Browser-only libraries:** render Leaflet only in client components (with SSR disabled for the map import). Use `next/font` or self-hosted assets for typography and Next.js navigation with `<Link>`; use Next.js App Router `loading.tsx`, `error.tsx`, `not-found.tsx` where appropriate. Keep the 24 specified URLs, implementing dynamic ids as `[id]` directories.

Do not substitute other frameworks or add a heavy microservice architecture without a compelling, documented reason. The app should run locally with simple, documented commands. External APIs must not be required merely to view the seeded demo.

## 5. Implementation principles

1. **Implement, don't just mock up.** Pages, forms, filters, controls, statuses, maps and metrics must connect to real application state or correctly labeled seeded demo fixtures.
2. **Build vertical slices.** PostgreSQL migration → Flask API → Next.js App Router page → tests for a complete use case, then proceed. Do not stop after a design-only phase.
3. **Maintain domain boundaries.** A batch groups requests; route stops represent pickups and drop-offs; tracking events record individual parcel progress; a partner assignment belongs to a batch.
4. **Validate at both ends.** Frontend validation improves UX; backend validation is authoritative.
5. **Explain decisions.** For each match display compatibility reasons, expected detour, distance estimates, and why any nearby request was rejected.
6. **Prefer real logic over decorative complexity.** A modest, correct constrained optimizer is better than an animated but fake “AI optimizer.”
7. **Keep a11y and responsiveness built in.** Semantic controls, keyboard flow, 4.5:1 body contrast target, visible focus, meaningful reduced-motion support.
8. **Avoid dead ends.** Every action has loading/success/error/empty states and meaningful validation.
9. **Use server authorization for every protected endpoint.** Hiding a button is not permission control.
10. **No hard-coded secrets.** Keep sample credentials and keys in development-only documentation and env/config.

## 6. Suggested monorepo layout

```text
/
├── agent.md
├── skill.md
├── design.md
├── README.md
├── .env.example
├── docker-compose.yml
├── frontend/                 # Next.js (App Router) application
│   ├── next.config.ts        # same-origin /api/v1 proxy to Flask API
│   ├── src/
│   │   ├── app/             # App Router pages, nested layouts, loading/error views
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   ├── auth/page.tsx
│   │   │   ├── customer/    # nested layouts and routes; [id] dynamic segments
│   │   │   ├── partner/
│   │   │   └── admin/
│   │   ├── components/      # server/client components; client-only map modules
│   │   ├── features/        # auth, requests, batches, tracking, reports
│   │   ├── lib/             # typed API client, Zod schemas, helpers
│   │   └── styles/          # tokens, Tailwind, global CSS
│   └── ...
├── backend/
│   ├── app/
│   │   ├── api/             # blueprints/controllers
│   │   ├── models/          # relational models
│   │   ├── schemas/         # request/response validation
│   │   ├── services/        # matching, routing, assignment, analytics
│   │   ├── security/        # RBAC, auth, CSRF, rate limits
│   │   └── ...
│   ├── migrations/
│   ├── tests/
│   └── ...
├── scripts/                # deterministic demo seeds
└── docs/                   # diagrams, API notes, assumptions
```

Keep application code in the **project root's frontend/backend structure**. Any folder labeled inspiration, references, or design examples is **read-only**; take inspiration, do not implement the project inside that folder.

## 7. Core entities

Model users, delivery partner profiles, recipient and authorized destination data, locations, requests, parcels, delivery batches, ordered batch stops/tasks, batch assignments/decisions, tracking events, notifications, issue reports and audit events. Normalize repetitive data when it simplifies correctness.

Use stable IDs, timestamps in UTC, explicit time zones for displayed schedules, foreign keys, indexes, uniqueness constraints and transaction boundaries. A request must expose a single authoritative status and its parcel must have its own execution status. Do not store mutable status solely in an event log without an efficient current-state projection.

## 8. Status model

- **Request:** `pending_matching → batched → assigned → in_progress → completed`, with controlled `cancelled`/`failed` branches.
- **Batch:** `proposed → offered → accepted → in_progress → completed`, with controlled `declined`/`cancelled` branches (a declined offer can be re-offered or released).
- **Parcel:** `pending → assigned → partner_accepted → pickup_arrived → picked_up → in_transit → delivered`, with `failed` when appropriate.
- **Issue reported:** preserve as a separate issue/event record; raising an issue does not necessarily erase the underlying execution status.

Transitions must be validated server-side. `delivered` cannot be set before `picked_up`; a customer cancellation must not silently invalidate an accepted/on-route delivery. Admin overrides require a reason and audit log.

## 9. Security baseline

- Hash passwords with Argon2id or a similarly modern adaptive password hasher; never log passwords or tokens.
- Use `HttpOnly`, `Secure` in HTTPS, appropriate `SameSite` session cookies; CSRF protection for mutating cookie-auth requests; strict origin/CORS configuration.
- Rate limit login and sensitive endpoints; sanitize output; validate all structured inputs; use ORM-bound parameters.
- Verify account ownership, partner assignment, and role rights on every read/write.
- Limit location/contact exposure: partners can access only the information necessary for accepted assignments; admins see what is operationally justified.
- Validate uploaded files by size/type if uploads are implemented; private storage/signed access where needed.
- Atomic assignment and booking; lock or compare-and-swap records so concurrent matches cannot claim the same request.
- Separate development demo data from production data; never ship active demo accounts in production.

## 10. Required test scenarios

- One product return and one ordinary parcel can coexist in a feasible shared batch with **different destinations**.
- Requests with nearby pickups but incompatible delivery windows **do not** match.
- A route never drops off a parcel before its pickup.
- Capacity is validated **after every stop**, including the size/weight load profile.
- Restricted or incompatible handling rules exclude invalid combinations.
- Decline/cancel/reassign flows release requests safely without duplicate active batches.
- A partner cannot edit an unrelated batch; a customer cannot read another customer's request; role-specific admin endpoints remain protected.
- Each parcel has independent tracking even when grouped with other parcels.
- Estimated savings are never presented as measured facts; negative savings do not become positive by rounding.
- All 24 source-defined views/routes resolve; primary forms and controls work at desktop and mobile widths.

## 11. Definition of done

The implementation is complete only when the developer can:
1. Start the app and database from a clean checkout using documented commands.
2. Log in as seeded customer, partner and administrator roles.
3. Submit a return and a regular parcel delivery request.
4. Run matching and inspect both successful and rejected candidates with explanations.
5. View a feasible route with ordered pickup/drop-off stops on a map or a clearly labeled route-estimate fallback.
6. Offer/assign, accept, execute and complete a multi-parcel batch.
7. See independent parcel tracking events, issue reporting and role-based history.
8. Inspect an admin sustainability dashboard with transparent **estimated** baseline methodology.
9. Run database migrations, unit tests, and a production build without unresolved critical errors.

## 12. Delivery behavior for the coding agent

- Inspect the existing repository first; preserve useful work.
- Create or update a compact task checklist internally, **then carry out the full build** without repeatedly asking permission to proceed.
- Choose reasonable defaults for missing non-critical details; state assumptions in README.
- Do not claim functionality is implemented unless code, data flow and tests substantiate it.
- If a live map/routing endpoint is blocked, implement the documented fallback rather than silently rendering fictional routes as live data.
- Finish with an accurate inventory of implemented features, commands to run, tests run, and any remaining limitations.
