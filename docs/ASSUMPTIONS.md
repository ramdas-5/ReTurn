# ReTurn assumptions and decisions

These are deliberate implementation choices where the brief left room for judgement.

## Matching and routing

1. **Baseline definition.** Each request's separate-trip baseline is one direct pickup → destination trip. The shared route and baseline use the same matrix (OSRM if reachable, otherwise the same labelled road-factor estimate). Partner repositioning to the first pickup is excluded from both.
2. **Service time.** A configurable 6 minutes per stop is included in scheduling and duration. It is not included in the distance baseline.
3. **Pickup radius.** 8 km is a coarse *prefilter* from the seed pickup, not approval. Every proposed group is still fully simulated.
4. **Detour.** A request's detour is the distance it travels from its pickup to its own drop-off along the shared route minus its direct pickup→drop-off distance. Default cap is 12 km; exceeding it rejects the insertion.
5. **Savings threshold.** Default minimum estimated saving is 12%. Zero, negative or sub-threshold groups are rejected; negative savings are never presented as positive.
6. **Reference vehicle.** If no verified/available partner fits, a preview may use the configured reference vehicle (40 kg / 0.25 m³) and the UI discloses that no partner is assigned. A real partner's capacity replaces it when offered/committed.
7. **Restricted handling.** A parcel flagged `restricted` requires a dedicated vehicle and cannot share a batch. Fragile parcels require `accepts_fragile` on the vehicle. Liquids are captured as handling metadata and require explicit vehicle support only through the fragile/restricted rules; no refrigerated or hazmat-specific model exists in the MVP.
8. **Partner availability.** Only `verified` + `available` partners are offered or offered-in-preview. Verification is an administrator action with an audit trail.
9. **One active reservation.** Enforced with a PostgreSQL partial unique index. Completed batch membership rows remain for history; `released_at` marks releases. A request in a terminal state is never eligible for matching regardless.
10. **Configurability.** Group size, radius, detour, savings threshold, service time, speed and road factor are per-preview parameters (bounded server-side) and defaults live in environment config. They are tuning choices, not universal optimums.

## Estimation honesty

- All distance/fuel/CO₂e figures are **modelled estimates**. The UI uses “Estimated” in labels and explains the factors.
- If OSRM is unavailable, distance is haversine × road factor and duration uses average speed; both map connectors and copy are labelled illustrative. No road navigation is implied.
- No live GPS or vehicle position is displayed, and no “live tracking” claim is made beyond parcel event history.
- Map tiles require network access; the app remains usable without them and labels missing geometry.

## Identity, privacy and security

- Sessions are server-side in PostgreSQL; only a SHA-256 hash of the random token is stored. The browser receives an HttpOnly cookie. `Secure` is enabled by configuration in HTTPS deployments.
- CSRF uses a double-submit cookie plus a session-bound token for authenticated mutations.
- Contact details are exposed only to the owning customer, the assigned partner after acceptance, and administrators. Customer batch payloads never include other customers' requests.
- No email delivery exists; notifications are in-app. Email preferences are stored and displayed but not dispatched.
- Rate limiting is in-process and aimed at a single-instance demo. Production should move it to a shared store.
- Demo accounts and seeded addresses are fictional and must not be enabled in production.

## Domain/product scope

- One time zone (`Asia/Kolkata`) is offered in the UI; timestamps are stored in UTC with timezone-aware columns. The schema allows more zones later.
- Delivery deadlines are hard. There is no partial-delivery or multi-attempt model beyond `failed`, an issue and manual resolution.
- A parcel has one item description with weight/volume and handling flags; multiple parcel rows per request are not implemented (one request = one parcel in the MVP).
- Customer cancellation is allowed while pending, or while the batch is still `proposed`. Once a partner accepts, online cancellation is blocked and support/issues are the route.
- Admin cancellation is blocked once a route is in progress. In-flight parcels are intentionally not silently discarded.
- Reassignment produces a fresh offer requiring partner acceptance; it does not force an assignment accepted on the partner's behalf.
- Partner verification does not expire automatically; admins can move a partner back to pending.

## Frontend decisions

- Next.js Server Components fetch the Flask API server-to-server and forward the user's cookie. The browser calls only same-origin `/api/v1` through a rewrite, avoiding CORS and keeping cookies first-party.
- Leaflet is client-only; dynamic import happens inside an effect. Marker popups are built with DOM text nodes rather than HTML strings to avoid injecting customer content.
- Guided request creation is a three-step client wizard (locations → parcel/schedule → review) with server-authoritative validation. Sample locations are fictional demo places; manual pins are supported.
- Tables reflow into cards below `md`. Partner controls use large minimum tap targets. Loading/error/empty states exist for the role shells and data views.
- Demo credentials are documented only in the README and seed script, not on public pages.
