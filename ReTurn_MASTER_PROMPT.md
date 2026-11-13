# ReTurn — Complete Master Build Prompt

> **How to use:** Place `agent.md`, `skill.md`, `design.md`, and this file in the root of your project. Open your coding agent in that root directory and paste the prompt below (or instruct it to execute this file). The instructions are intended for a **complete implementation**, not merely a UI mockup.

---

## PROMPT START 

You are the principal full-stack engineer, logistics-domain architect, product designer, security engineer, QA engineer and technical writer for my product **ReTurn**.

**Build a complete, production-minded, hackathon-demonstrable web application called ReTurn — Smart Reverse Delivery & Shared Logistics Platform. Keep the name ReTurn unchanged.**

**Tagline:** One Route. Multiple Deliveries. Less Waste.

**One-line vision:** Make separate e-commerce returns and ordinary parcel deliveries share sensible routes whenever their actual operational constraints allow it.

### Mandatory context and reading order

Before implementing anything:

1. Inspect the actual repository and existing code/assets; do not overwrite useful work unnecessarily.
2. Read `/agent.md` for engineering instructions and definition of done.
3. Read `/skill.md` for product workflows, data model, route matching, endpoints, page list and demonstrations.
4. Read `/design.md` for the distinctive ReTurn design language, tokens, layouts, components, responsive interactions and truthful visualization rules.
5. If available, read the original source document `ReTurn_Detailed_Project_Explanation(3).md`. It defines **ReTurn** as the official project name. **Do not rename this project.** Preserve the exact capitalization `ReTurn` in all user-facing brand references.

If an instruction is not explicit, make a defensible engineering/design decision, implement it and document the assumption. **Do not repeatedly ask me for approval between phases.** Complete the system, not just skeletons, generated marketing pages or a design file.

### What ReTurn must do

ReTurn is a coordination and route-planning platform that does not need to own courier vehicles. There are exactly two main customer services:

- **Return a Product:** customer supplies a pickup location, parcel details, pickup window, and the **authorized return destination** (plus optional return reference).
- **Send a Parcel:** customer supplies pickup location, **recipient delivery address**, recipient information, parcel details, and delivery constraints.

The system finds requests that are compatible **as a whole** and groups them into proposed delivery batches. Different parcels can have **different authorized destinations**, even when grouped. A batch contains an ordered sequence of pickups and deliveries. A verified partner accepts the assignment and updates the **status of each parcel separately**. Customers track their own requests, and admins monitor, manage and analyze operations.

The **core feature** is an actual **explainable, constraint-aware matching and routing engine**. Do not fake matching by always grouping the three nearest requests. Reject infeasible batches and show **why**.

### Required technology choices

Use the architecture described in `agent.md` and `skill.md`, particularly:

- **Frontend (mandatory):** **Next.js (App Router) + React + TypeScript**, Tailwind CSS, accessible components, Lucide icons, TanStack Query where useful, React Hook Form and Zod. **Do not use Vite or React Router.**
- **Backend:** Python + Flask with structured REST API, SQLAlchemy ORM and Alembic migrations.
- **Database (mandatory):** **PostgreSQL** with real persisted state, relational constraints and indexes, managed by Flask/SQLAlchemy + Alembic. **Do not substitute SQLite or MySQL as the primary database.**
- **Maps:** Leaflet with OpenStreetMap attribution.
- **Routing:** OSRM road route/duration when reachable; a **clearly labeled demo/approximation fallback** when it isn't.
- **Matching:** implemented in Python using explainable rule-based compatibility and a practical constrained route-insertion heuristic. Do **not** describe rule-based logic as trained AI or imply a trained model exists.
- **Auth:** hardened server-side session-based login/registration, role-based authorization, protected mutations, CSRF handling and rate limiting.
- **Local development:** working Docker Compose configuration where practical, `.env.example`, migration and deterministic seed commands, concise README.

Use sensible libraries where helpful, but avoid unnecessary microservices, hosted-only dependencies and secret API requirements for the basic demonstration.

### Next.js integration requirements

- Build the frontend in `/frontend` using the **Next.js App Router** (`src/app/`, `layout.tsx`, `page.tsx`, `loading.tsx`, `error.tsx`, and `[id]` route segments). Preserve exactly the 24 requested pages/URLs in `skill.md`.
- Keep Python Flask as the authoritative REST backend. The browser should call a **same-origin** `/api/v1/*` endpoint proxied to Flask via a configurable Next.js rewrite or an equivalently secure architecture. Keep authentication cookies and CSRF protection working through local development and Docker, and document the strategy.
- Use Next.js Server Components for safe initial composition and Client Components for interactive tables/forms/dialogs, Leaflet and route execution. Load Leaflet only in the browser.
- For authenticated data, explicitly avoid public caching and static rendering; enforce all sensitive access at the Flask API level. Do not expose `DATABASE_URL`, Flask session secrets or service tokens through `NEXT_PUBLIC_*` variables.
- Use Next.js's navigation, metadata and responsive nested role layouts. Provide working `npm run dev`, `npm run build`, lint/typecheck/tests and Docker/local startup instructions. Keep PostgreSQL persistence real and run migrations.

### Three user roles and functional scope

**Customer:** register/login, choose return or parcel, submit and validate real requests, view own dashboard/list/details/history, track parcel-level events, cancel when allowed, report a delivery issue, manage profile.

**Delivery Partner:** register/login, maintain vehicle capacity/service area/availability, await administrator verification, view offered/assigned batches, accept/decline, see ordered stops on map, execute pickups/deliveries, update each parcel through valid statuses, report issues and review completed work.

**Administrator:** see operational dashboard; manage customer and partner accounts, verify partners, view requests; run matching preview and commit feasible batches; manually offer/assign/reassign with audit trails; monitor routes; handle issues; view operational KPIs and estimated sustainability reports.

Implement the **24 functional views** explicitly listed in `skill.md`: 9 customer-facing/public views, 7 delivery partner views and 8 admin views. Use reusable layouts and components, but do not omit role-specific screens or leave any as an empty placeholder. Include proper login/register, session recovery, access denied, not found and validation/error states.

### Core engine specification (most important)

For every proposed grouping, enforce:

1. Valid pickup and drop-off locations with destination identity preserved.
2. Compatible pickup windows; feasible delivery deadlines and arrival/service timing.
3. A real ordered itinerary with **pickup before delivery for every request**.
4. Vehicle **weight/volume capacity at every segment of the route**, including load released at drop-offs.
5. Compatible handling requirements (fragile/restricted/etc.) and service areas.
6. Partner verification, availability and vehicle eligibility before offering/assigning.
7. A **meaningful, positive operational benefit** compared to a stated separate-trip distance baseline.
8. No customer request reserved in more than one active proposal/batch, including concurrent requests.

Implement a small, deterministic feasibility/route heuristic for a real MVP (e.g., candidate filtering + insertion of pickup/drop-off pairs into ordered stop lists). Allow configurable constraints. Evaluate several proposed groups, not just one fixed fixture. The engine must produce **explanations** for successful matches and reasons for near-misses or rejections.

Store the proposed route, ordered stops, method/source of distance estimates, comparison baseline, assumptions and decision data. Build the matched-request preview, not merely a “Run AI” button. Validate again on commit and make all assignment/status mutations transactional.

### Route and environmental honesty

If a road-routing service works, display its valid road polyline and travel estimates. If it fails, the application must still work for a local demo using deterministic estimated stop ordering, but label any straight-line connections or inferred distance **Illustrative / estimated — not road navigation**. Do not render invented live courier GPS data.

All distance, trip, fuel and emissions benefits must be labeled **estimated**. Compare baseline and grouped route on the same assumptions; show the assumptions and factors. Do not claim that a certain number of vehicles or trips were definitely eliminated or that emissions were measured.

### Design requirement — premium and distinctive

Follow `design.md` precisely. **ReTurn should look like a deliberately designed urban-route operations product, not generic template UI or an AI-generated dashboard copy.**

- Brand system: deep ink, muted pale-canvas surfaces, refined jade/teal route emphasis, restrained lime details, service-specific blue, clear warning/red states.
- Typography: Plus Jakarta Sans for expressive headings, Inter for body, limited IBM Plex Mono for IDs/data.
- Strong identity: route-thread motif, consistent pickup vs drop-off markers and clear service-type iconography.
- Public landing: impressive editorial dark hero, elegantly illustrated multi-stop neighborhood route, clear dual service CTAs, truthful process explanation.
- Customer: welcoming, clear dual-service creation cards, responsive guided forms, actual parcel tracking/history.
- Partner: high-contrast mobile-first route execution, next stop, large legal action controls, stop sequence/map.
- Admin: polished operations center with meaningful stats, match queue, feasibility details, route monitoring and issues.
- Use semantic design tokens, excellent spacing, purposeful cards, calm transitions, skeleton/error/empty states, accessible focus and mobile layouts.

Do not install a completely different design system midway. Avoid excessive gradients, random oversized charts, decorative maps with false data, and buttons that are not connected to actions.

### Data model and API

Create real relational models, migration scripts, API schema validation and tests. At minimum support: users, partner profiles, locations, requests, parcels, service-specific destination/recipient details, batches, ordered stops, assignments/offers, tracking events, notifications, issues and admin audit events. See the precise definitions in `skill.md`.

Implement REST endpoints for auth/session, request CRUD/filtered list/detail/cancel, batch preview and commit, offer/decision/reassign, parcel status events, partner verification, issues, notifications, analytics and profile settings. Follow permission-scoped queries everywhere; do not trust user-supplied IDs for ownership or calculations.

State transitions must be guarded: you may not deliver a parcel before pickup, nor edit another partner's batch. A batch never replaces independent parcel tracking. Cancellation, decline and reassignment must not duplicate reservations or erase history.

### Security and engineering quality

- Hash passwords securely, use secure HttpOnly cookie sessions and CSRF protection for cookie-auth mutations.
- Validate all payloads, constrain CORS/origins, protect ownership and roles at the API level, and rate limit sensitive endpoints.
- Implement transactions/locking against double grouping and double assignment.
- Store secrets in environment variables; ship only example env values.
- Respect privacy: customer contact/address details must be exposed only to the corresponding user or an authorized operational actor.
- Treat dev demo accounts and seeded addresses as **fictional/sample** data; don't ship them into production.
- Add concise logs and consistent error envelopes; handle unavailable routing/map services and network failures gracefully.
- Ensure the app builds, can be run from a fresh checkout, and has runnable migrations/seeds/tests.

### Required real demo data and narrative

Seed a small, repeatable **fictional** scenario based on the brief:

1. Rahul wants to return shoes from Barasat to an authorized return hub.
2. Priya wants to send a book from a nearby pickup to a recipient in Salt Lake.
3. Amit wants to return headphones from nearby Barasat to an authorized return hub.

Provide illustrative but sensible windows, parcel weights and vehicle capacity such that this example is feasible **if** it genuinely passes engine checks. Also include at least two counterexamples (e.g., incompatible deadline and capacity/handling conflict) to prove the engine does not group everything nearby.

Seed one admin, one verified partner and at least three customer demo accounts, with credentials declared **only in development documentation**. Demonstrate: customer submissions → admin pending queue → matching preview/explanation → commit shared batch → offer → partner acceptance → route stop execution → individual parcel tracking → admin estimated impact dashboard.

### Required tests and quality gates

Provide meaningful unit/integration coverage for:

- Mixed return + ordinary parcel group with **different destinations**.
- Time-window, deadline and handling/capacity rejections.
- Pickup-before-delivery and capacity load updates at every stop.
- No duplicate active batch reservation under concurrent use.
- Auth, role permissions, ownership, partner verification and legal status transitions.
- Proposed batch lifecycle, accept/decline/reassign, parcel tracking histories.
- Estimated baseline/savings math and honest fallback labels.
- Core request forms, loading and error states, responsive smoke tests, page rendering.

Run the available linters/type checks/tests/build and fix issues. Do not report "all tests passing" unless you actually ran them. List any remaining real gaps explicitly.

### Deliverables to create in this repository

1. Fully functional **Next.js App Router + TypeScript frontend**, including the 24 views, role-specific nested layouts and complete responsive design system.
2. Flask REST API and **PostgreSQL** models/Alembic migrations, matching/routing/assignment/services and strong authorization.
3. Functional role-specific sessions and end-to-end request, batch and parcel workflows.
4. Map/route module with accurate fallback handling and disclaimers.
5. Seed data, sample demo credentials (development only) and explainable matching example.
6. Docker/local configuration, `.env.example`, readable README, API proxy/auth notes, tests and working **Next.js production build** commands.
7. A final concise report covering implemented functionality, commands, checked tests and actual limitations.

### Execution rules — critically important

- **Start now and carry the project through end to end** without stopping after planning, wireframes, theme creation, or authentication scaffolding.
- Do **not** require my approval after each phase. Decide minor details and proceed.
- Work in the actual project root. Any folder named `inspiration`, `reference`, or `frontend-ref` is inspiration-only: you may inspect assets, but never create the main app inside it or make the main app dependent on it.
- Reuse legitimate existing code; remove or replace broken scaffolding thoughtfully.
- Prioritize an accurate complete vertical workflow over speculative feature bloat.
- Do not introduce payment gateways, real courier/ecommerce integrations, GPS telemetry or ML dependencies into the MVP just to make the project appear advanced.
- No fake controls, nonfunctional CTA buttons, hard-coded data pretending to be persisted records, or placeholder dashboards.
- **Brand-lock rule:** The official name is **ReTurn**, exactly as in the original brief. Never rename it, change the capitalization, invent a different product identity, or refer to it as a former name.
- The final system must demonstrate the product's core innovation: **separate compatible requests → one feasible shared multi-stop route → partner execution → parcel-level tracking → transparent estimated benefit**.

**Now inspect the repo, follow `agent.md`, `skill.md` and `design.md`, implement the complete project, and verify it with real test/build commands.**

## PROMPT END
