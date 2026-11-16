# ReTurn assumptions and decisions (v2)

## Product and roles

1. Only consumers self-register. Drivers and managers are provisioned by administrators; drivers may also be provisioned by managers. Administrators are created through the bootstrap command/environment, not public signup.
2. A driver must be verified, on a live duty session, covered by the pickup service area and using a verified active vehicle before assignment. These rules are revalidated at assignment and suggestion approval.
3. A manager sees only orders whose pickup area is in their assigned service areas. Administrators see all orders.
4. Consumers may cancel only before the parcel is in a driver's custody. After that, support/issues is the route.
5. Delivery completion requires a captured photo when `DELIVERY_PROOF_REQUIRED=true` (the default). A failed capture is an exception, not a completed delivery.
6. Pickup proof is optional by default (`PICKUP_PROOF_REQUIRED=false`) but the API and UI support it.
7. Proof location is required by default (`PROOF_REQUIRE_GPS=true`) and validated against the stop radius and accuracy limits. A browser may deny location; the driver is then shown an explicit error rather than an invented point.

## Matching and routing

1. Matching is a deterministic insertion heuristic over each driver's **active route**, not machine learning and not an exact solver.
2. Suggestions are persisted with score, detour, added duration, reasons, blockers and a capacity snapshot. They expire after `suggestion_ttl_minutes`.
3. Manager approval re-runs the full evaluation before assignment; stale or expired suggestions are refused.
4. `max_pickup_radius_km` is a corridor prefilter, not approval. Full capacity, window, deadline, precedence and detour checks still run.
5. `max_detour_km` limits how far the route may grow. The added duration is an estimate from the routing source.
6. Administrator matching overrides are stored in `admin_settings` and merged over environment defaults. They affect new plans and scans immediately.
7. OSRM is used when reachable. On failure, distance is haversine × road factor and duration uses average speed; labels and dashed map connectors state that this is an estimate, not road navigation.
8. Fuel and CO₂e are modelled from stored distance and configurable factors. They are never measured telemetry and negative savings are clamped to zero.

## Proof and location privacy

1. Location is collected only while a driver is on duty and explicitly consents in the request. ReTurn does not track off-duty drivers.
2. The platform shows only the latest reported point and labels it live recent, stale or unavailable. It does not interpolate or fabricate positions.
3. Proof media is private and served only through signed, expiring URLs with authorization checks.
4. Local media storage is a development fallback. Hosted deployments should use S3 because container filesystems are ephemeral.

## Accounts and security

1. Sessions are server-side in PostgreSQL; only a token hash is stored. Cookies are HttpOnly and `SameSite=Lax`; `Secure` must be enabled on HTTPS.
2. CSRF is a double-submit cookie plus a session-bound token.
3. Rate limiting is in-process and intended for a single instance. Multi-instance deployments need a shared store or gateway.
4. Reset and activation tokens are returned in development when `AUTH_EXPOSE_RESET_TOKENS=true` because no email provider is configured. This must be disabled in production with a real email integration.
5. Account suspension, verification, service area and matching configuration changes are audited.

## Frontend

1. Role layouts guard navigation with `requireUser(role)`; every action is still authorized by Flask.
2. Client pages fetch real API data with TanStack Query. There are no hardcoded dashboard metrics.
3. The consumer booking form requires either an exterior photograph or a written exception of at least 12 characters.
4. Availability shown before booking is calculated from stored service areas, verified schedules and live duty sessions. It is not a driver commitment.
5. Maps are illustrative route visualisations, not live navigation or vehicle telemetry. Navigation links open Google Maps directions to a stop.
6. Demo seed data is fictional and must not be enabled where real data is stored.

## Known scope limits

- No email delivery, MFA, payments or e-commerce integration.
- No automated browser E2E suite; verification is API tests plus frontend typecheck/lint/unit/build.
- Multi-parcel-per-order and multi-city tenancy are not implemented.
- Public OSRM is best-effort and may rate-limit.
