# ReTurn — DESIGN.md

> Implementation-ready brand, UI, interaction and accessibility specification.
> Design direction proposed for this build: **Urban Route Studio** — elegant city-logistics operations, tactile maps, precise data, understated motion.
> This is a creative design system layered onto the source project's functional requirements.

## 1. Brand and creative direction

**Name / wordmark:** **ReTurn**, with exactly this mixed-case capitalization in the logo, hero, navigation, document titles and metadata. Do not render the project name as all-caps or replace it with any alternate brand.

**Category:** Smart Reverse Delivery & Shared Logistics Platform

**Tagline:** One Route. Multiple Deliveries. Less Waste.

**One-sentence proposition:** Combine compatible returns and deliveries into smarter shared routes.

**Audience:** everyday parcel senders/return customers; independent delivery partners; logistics administrators and hackathon reviewers.

**Visual personality:** confident, useful, precise, welcoming, local-first, modern. Not generic “SaaS purple,” not a food-delivery clone, not a crypto dashboard. Emphasize networks, routes, parcel journeys, city maps, and measurable efficiency.

### Signature idea

The recurring product motif is the **route thread**: a subtly curved path linking a **pickup circle** and **delivery square**, optionally with intermediate stops. Use it in the logo mark, hero illustration, progress indicators and empty-state art. This must remain a functional route metaphor; never imply that a return's drop-off is the same as a regular parcel's destination.

## Frontend implementation contract — Next.js

This design system is implemented in **Next.js (App Router) with TypeScript and Tailwind CSS**, not in a Vite/React Router single-page application. Use the same design language across Server Components and Client Components.

- Build the public landing page at `src/app/page.tsx`, auth at `src/app/auth/page.tsx` and role-aware nested `customer/`, `partner/` and `admin/` layouts using Next.js file-system routes.
- Prefer `next/font` (or local font assets) for Plus Jakarta Sans, Inter and IBM Plex Mono, and use `next/link` for navigation. Reuse semantic Tailwind/CSS token values in both server-rendered and interactive components.
- Keep personalized operational screens and sensitive customer data uncached per user; do not statically publish role-specific pages or sensitive metadata.
- Render Leaflet/OSM components client-side only because browser map APIs are unavailable during server rendering; give them useful loading, route-failure and no-network states.
- Implement working Server Actions only if they preserve Flask as the authoritative API for validation, auth and business rules; otherwise use typed client calls to the same-origin Flask API proxy.
- Configure accessible metadata, semantic landmarks, `loading.tsx`, `error.tsx`, and responsive navigation for all role shells. **PostgreSQL** backs all persisted operational data through Flask; never show hardcoded UI fixtures as if they are live records.

## 2. Design tokens

Implement as CSS variables and mirror into Tailwind. Use semantic tokens rather than scattered hex values.

### Colors — light theme (default)

| Token | Value | Usage |
|---|---|---|
| `--ink` | `#142A29` | Primary text and dark sidebar |
| `--ink-2` | `#274442` | Secondary dark surfaces/headings |
| `--canvas` | `#F6F8F5` | App background |
| `--surface` | `#FFFFFF` | Cards and sheets |
| `--surface-muted` | `#EEF3EF` | Grouped/filter controls |
| `--line` | `#DFE7E1` | Borders and separators |
| `--muted` | `#5E726F` | Secondary text |
| `--accent` | `#087C60` | Primary buttons, route emphasis (accessible on white) |
| `--accent-strong` | `#075C49` | Hover/pressed |
| `--accent-soft` | `#DDF3E9` | Success/selected backgrounds |
| `--lime` | `#CBF08C` | Sparse expressive highlights, never primary body text |
| `--amber` | `#E8A33C` | Warning and in-progress accents |
| `--amber-soft` | `#FFF1D6` | Warning backgrounds |
| `--red` | `#B74444` | Error and destructive states |
| `--red-soft` | `#FBE9E6` | Error backgrounds |
| `--blue` | `#2C6CA2` | Parcel/service secondary lane |
| `--blue-soft` | `#E6F1F9` | Parcel/delivery backgrounds |

Avoid low-contrast accent text; use deep ink on lime. Use palette on maps/charts, with redundant patterns, labels and marker icons.

### Optional dark mode

| Token | Value |
|---|---|
| `--canvas` | `#0E1B1A` |
| `--surface` | `#172927` |
| `--surface-muted` | `#213633` |
| `--line` | `#35504A` |
| `--ink` | `#F0F7F2` |
| `--muted` | `#B3C7BE` |
| `--accent` | `#67DDB0` |

Dark mode is optional; a coherent, fully functional light theme is more important than two partial themes.

### Typography

```text
font.family.display = "Plus Jakarta Sans", "Inter", Arial, sans-serif
font.family.body    = "Inter", Arial, sans-serif
font.family.mono    = "IBM Plex Mono", ui-monospace, monospace
font.size.xs        = 12px / 18px
font.size.sm        = 14px / 20px
font.size.base      = 15px / 24px
font.size.lg        = 17px / 26px
font.size.h4        = 20px / 28px
font.size.h3        = 26px / 34px
font.size.h2        = 34px / 42px
font.size.h1        = clamp(40px, 5vw, 68px) / 1.05
font.weight.body    = 400
font.weight.medium  = 500
font.weight.heading = 700
```

Use tabular numerals for distances, ETAs and KPI metrics. Use mono sparingly for IDs (`RTN-REQ-1024`, `RTN-BAT-207`) and timestamps; avoid walls of uppercase monospaced copy.

### Radius / spacing / effects

```text
spacing.base    = 4px (multiples of 4)
container.max   = 1440px
sidebar.width   = 252px
header.height   = 72px
radius.control  = 10px
radius.card     = 16px
radius.modal    = 22px
shadow.card     = 0 6px 24px rgba(15, 40, 32, 0.045)
shadow.floating = 0 14px 42px rgba(9, 37, 31, 0.13)
```

Cards have 1px borders, airy 20–28px padding, subtle shadows only where hierarchy demands. Prefer 12/16/24/32px gaps. Keep density purposeful in dispatch tables.

## 3. Page architecture / navigation

### Public / customer

Public landing uses a bright editorial layout with a dark inky hero and a route visualization. Customer shell uses a left desktop sidebar, top command/search/action bar and spacious cards. Main actions are **Return a Product** and **Send a Parcel**; never hide both inside a vague “Create order” menu.

Customer menu: Overview · My Requests · Request History · Profile & Settings. Creation actions are always visible near the top. Tracking/detail views show a clear timeline and destination type.

### Delivery partner

Partner shell is optimized for **outdoor/mobile use**: high contrast, tap targets ≥44px, immediate next-stop display, route map, stop list and obvious state-change buttons. Desktop keeps a narrow operational rail; mobile uses bottom tabs or compact header/actions.

Partner menu: Overview · Available Batches · Active Route · Completed Work · Vehicle & Profile.

### Admin

Admin shell is a serious but friendly **dispatch control room**: dense operational data, 2-column contextual content, a large map where relevant, consistent filters and a visible active-work queue.

Admin menu: Overview · Requests · Batches · Route Monitor · Customers · Partners · Issues · Analytics.

### Navigation behavior

Use route-aware nav active states, breadcrumbs for detail pages, role-sensitive account switch only if the logged-in user truly has permissions, and a functional notification menu. Never show admin links to customers. Auth error/forbidden/not-found screens should be branded and offer a useful return path.

## 4. Signature screen compositions

### Landing page (`/`)

- **Header:** route-thread logo + `ReTurn` wordmark, How It Works, Services, Impact, Login and **Get Started**.
- **Hero:** dark ink background; very large headline “Fewer trips. Smarter deliveries.”; supporting explanation; CTA **Send a parcel** and secondary **Return a product**.
- **Hero visual:** elegant illustrative neighborhood map with 3 separate pickup markers converging into a feasible multi-stop route; a small badge **3 requests · 1 coordinated batch** marked **Illustrative scenario**.
- **Trust section:** “What ReTurn checks” with time, capacity, route, destinations and handling icons.
- **Process section:** Create → Match → Share a route → Track, with route-thread connector.
- **Impact:** explain that distance, fuel and CO2e savings are **estimates**, not guaranteed measured facts.
- **Footer:** scope, roles, access and attribution for map data where applicable.

### Customer dashboard (`/customer`)

- Greeting and active-request card with precise next action.
- Two large side-by-side service cards: **Product Return** (teal pickup/return icon) and **Send a Parcel** (blue destination arrow icon).
- Status summary: active, pending match, completed.
- Recent request list with service type, origin → authorized destination/recipient, compact status chips, updated time and View Details.
- Helpful empty state for a customer with zero requests; never show fictional active orders by default.

### Create request views

Use a 2-column layout on desktop: 65% clean multistep form, 35% summary/map preview. Stages: Service → Locations → Package → Schedule → Review. Show progress and allow back/edit. Destinations are intentionally distinct:

- Return: `Authorized return destination` (required), optional `Return reference`.
- Parcel: `Recipient delivery address` and recipient details (required).

Capture address plus coordinates through a map pin or place search with review. Never submit an unresolved/ambiguous location without a clear prompt. Capture pickup window, weight/size and handling notes. On review show **ReTurn checks compatibility after submission; grouping isn't guaranteed**.

### Customer tracking (`/customer/requests/:id`)

- Header: tracking ID, service type, actual current status, request date.
- Large horizontal or vertical **parcel-level** status timeline.
- Pickup card → destination card; name the **authorized return hub** when applicable.
- Map preview if geolocations exist; route display only once assigned and permitted.
- Assigned partner summary where valid, notification history, report issue action.
- Distinguish `Pending match`, `Proposed batch`, `Partner accepted`, `Picked up`, `In transit`, `Delivered` without asserting everything is live GPS.

### Partner dashboard / route

- Hero panel: **Next stop**, stop type, service window, number of parcels currently loaded.
- Primary actions: **Start route** / **Arrived** / **Confirm pickup** / **Confirm delivery**, shown according to legal state.
- Map + ordered stop rail: numbered stops with **pickup circle** or **drop-off square**, status, parcel tracking ID and compact instructions.
- Offline/error behavior: routing service unavailable banner with preserved stop sequence, not a fabricated road trace.
- For each parcel, show individual current state and proof/issue actions.

### Admin dashboard

- Four restrained KPI cards: Pending Requests, Proposed Batches, Active Routes, Completed Parcels.
- Main central split: **matching opportunities / requests queue** + **route overview map**.
- Context sidebar: unresolved issues, pending partner verifications, recent batch actions.
- Clear accent primary CTA: **Run Smart Matching**; show work state and preview, not instant magic numbers.
- “Why matched” details panel explaining compatible window, capacity, route and distance assumptions.

### Batch management

Use a master/detail pattern:

| Left/table | Right/detail panel |
|---|---|
| Batch ID, parcel count, state, estimated savings, eligibility | Map + ordered stops, load curve, reasons, delivery deadlines, partner options |

Actions **Preview**, **Create Batch**, **Offer**, **Reassign**, **Cancel** must call distinct endpoints and require appropriate confirmations/reasons. Rejections should be inspectable and educational, not silent.

### Analytics + sustainability

Use attractive but honest line/bar visuals: requests over time, fulfilled parcels, batch utilization, service mix and estimated distance comparison. An illustrative `Before` vs `Shared plan` chart is allowed only when both numbers use the **same stated estimation method**. Show factor inputs/assumptions in a methodology panel.

Labels should literally read `Estimated distance saved`, `Estimated fuel saved`, `Estimated CO₂e avoided`. Include source of route measurement and note that results are modeled estimates.

## 5. Components inventory

**Primitives:** Button (primary/secondary/ghost/destructive), Input, Select, Combobox, DateTime range, Checkbox, Stepper, Drawer, Modal, Tooltip, Snackbar, Skeleton, Empty State, Confirm Dialog, DataTable, Pagination, Tab, Search, Filter chips, Badge, Avatar, Breadcrumb, Toast.

**Domain components:**
- `BrandLogo` with route-thread symbol.
- `ServiceTypeCard` — Return vs Parcel.
- `ParcelStatusBadge` and `BatchStatusBadge` (separate taxonomies).
- `RequestCard` and `RequestTable`.
- `ParcelTimeline` with event actor/time/notes.
- `RouteMap` with Leaflet and map attribution.
- `RouteStopList` with pickup vs drop-off iconography.
- `BatchCompatibilityPanel` with inclusion and rejection explanations.
- `VehicleCapacityIndicator` / load-by-stop bar.
- `SavingsComparison` with explicit `Estimated` labels.
- `DispatchActionBar` with permission- and state-based actions.
- `IssueSeverityBadge` and `ActivityFeed`.

Every data visualization must have a readable text equivalent or accessible label. Use well-defined icons from Lucide rather than inconsistent emoji in controls.

## 6. Semantic service / status indicators

**Service identity:** returns use **teal** with a ↩-style icon; regular parcels use **blue** with a package/arrow icon. Never use color as the only distinction.

| Status family | Visual treatment |
|---|---|
| Pending / unassigned | gray/neutral chip, clock icon |
| Proposed / offered | blue-outline chip, layers icon |
| Accepted / active | teal chip, navigation/route icon |
| Pickup arrived / in transit | amber chip, moving-dot icon |
| Delivered / complete | soft green chip, check icon |
| Issue / failed | red chip, alert triangle icon |
| Cancelled | neutral muted chip, ban icon |

Statuses must reflect backend truth. Show exact next actions; don't fake animated progress.

## 7. Data and map visualization

- Map base: neutral OSM tiles, correct attribution; include graceful no-network state.
- Stops: numbered markers and distinguish pickup/delivery with shapes/icons; highlight next stop.
- Road polyline only when sourced from valid routing result; fallback straight connectors must be labeled *illustrative*.
- Keep route lines sufficiently thick and accessible; charts should not depend on tiny text.
- Show `km`, arrival window, parcel load and route method adjacent to maps.
- Use modest microinteractions: stop marker hover/focus, route-table sync, sequence progress.
- No real-time vehicle dots unless live position data actually exists; demo positions explicitly named `Simulated`.

## 8. Responsive behavior

| Viewport | Layout |
|---|---|
| ≥1280px | Full sidebar, spacious table/map split, 4 KPI columns |
| 1024–1279px | Collapsible sidebar, 2–3 KPI columns, resilient detail drawers |
| 768–1023px | Compact nav, 2 KPI columns, stacked map and data |
| <768px | Bottom/collapsible navigation, one-column cards, sticky action area on route view, large tap targets |

Tables must reflow into meaningful compact rows/cards on mobile; avoid sideways overflow as the sole solution. Place major actions within thumb reach on partner screens. Ensure modals fit viewport height and support keyboard dismissal safely.

## 9. Motion and interaction

- Typical interaction transition: 140–200ms for opacity/transform; no long page transitions.
- Loading skeletons only while actually loading; avoid permanent fake shimmer.
- Matching action can show a structured progress state followed by **actual** preview output and reasons.
- Route line drawing on first reveal may be tasteful (<600ms), but must not distract from work.
- Respect `prefers-reduced-motion`.
- Confirm destructive actions; optimistic update only with rollback and correct concurrency handling.

## 10. Accessibility and content quality

- Aim for WCAG 2.2 AA contrast and keyboard behavior.
- Provide field labels, inline errors and summary at submit; associate errors programmatically.
- Focus management for drawers/dialogs; visible focus ring; no icon-only unlabeled actions.
- Body copy clear and approachable; no inflated AI claims or eco promises.
- Design empty/error/slow-network states for **every** core page.
- Proper 24-hour or locale-aware time formatting; default to `Asia/Kolkata` for the demo but store in UTC.
- Keep all sensitive contact information out of public and unauthorized contexts.

## 11. Copy system / microcopy

Preferred labels:

```text
Primary service actions: Return a product / Send a parcel
Matching call-to-action: Find compatible requests
Successful grouping: Compatible requests grouped into a proposed batch
Warning: Nearby does not always mean compatible
Tracking empty state: Your parcel journey will appear here after you submit a request
Routing fallback: Road routing is unavailable. Showing an illustrative stop sequence.
Analytics disclosure: All savings are estimates based on modeled routes and stated assumptions.
Return destination field: Authorized return destination
Parcel destination field: Recipient delivery address
```

Avoid: “AI-powered guaranteed savings,” “Live tracking” without telemetry, “100% eco-friendly,” “instant shipment,” and “all parcels go to return hub.”

## 12. Acceptance criteria for design

- A reviewer recognizes ReTurn in ≤5 seconds and understands the two service types.
- Navigation and main CTA are obvious for each role.
- Customer creation feels calm and comprehensible; partner execution is operationally quick; admin actions are auditable and information-rich.
- All 24 views are visually coherent without copy-pasting an identical placeholder dashboard into each route.
- Maps, statuses, form controls and savings panels convey **truthful, usable** information.
- Visuals are polished and distinctive: route-thread, quiet green palette, excellent spacing, precise type, high-quality icons and meaningful data hierarchies.
