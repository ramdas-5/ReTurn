# ReTurn — Complete Project Transformation & Implementation Master Prompt

## 1. Your Mission

You are a senior full-stack software engineer, logistics systems architect, database engineer, UI/UX designer, and quality assurance specialist.

Your task is to **transform my existing project, ReTurn, into a complete, functional, modern, intelligent delivery and reverse-logistics platform**.

**Project name: ReTurn**

**Tagline: One Route. Multiple Deliveries. Less Waste.**

Do not rename the project.

This is an **existing project** with working source code, authentication, frontend screens, backend APIs, PostgreSQL database models, Docker configuration, and deployment setup.

Do not create a completely unrelated application. Inspect the existing codebase, reuse working components where appropriate, fix incorrect logic, and replace features that do not meet the new requirements.

The previous version focused mainly on collecting customer requests, grouping them, and assigning batches.

The new version must function more like a complete delivery-management platform for:

- E-commerce businesses sending customer orders.
- Individual consumers sending parcels.
- Customers returning products to businesses.
- Delivery partners collecting and delivering parcels.
- Managers managing drivers, orders, batches, and delivery operations.
- Administrators controlling the entire platform.

The biggest innovation must be **intelligent route-aware pickup and delivery matching**.

If a delivery driver is already travelling along a route, and a compatible new parcel request appears along or near that route, ReTurn should identify the opportunity and recommend that task to the responsible manager.

The manager can review the recommendation and assign it to the driver if operationally feasible.

The application must become a **real working system**, not just a UI demonstration.

---

## 2. Mandatory Technology Stack

Use the following technology stack.

### Frontend

- Next.js App Router
- React
- TypeScript
- Tailwind CSS
- Reusable UI components
- Responsive dashboard architecture
- TanStack Query or an equivalent robust data-fetching solution
- React Hook Form and Zod for validated forms
- Leaflet with OpenStreetMap for maps
- Modern charting libraries for analytics

### Backend

- Python
- Flask REST API
- SQLAlchemy ORM
- Alembic migrations
- Pydantic or Marshmallow for validation
- Secure authentication and authorization
- Server-side business logic

### Database

- PostgreSQL
- Neon PostgreSQL for production if already configured

### Maps and Routing

- OpenStreetMap
- Leaflet
- OSRM or a compatible road-routing service
- Browser Geolocation API for authorized driver tracking

### Media Storage

- Use secure object storage such as Cloudinary or S3-compatible storage for parcel photographs and delivery proof images.
- Use a clearly documented local-development storage adapter if cloud credentials are unavailable.

### Deployment

- GitHub
- Vercel for the Next.js frontend
- Render for the Flask backend
- Neon for PostgreSQL
- Docker for local development

Use a currently supported, security-patched Next.js release. Do not retain the previously vulnerable Next.js 15.5.4 version.

Keep the application compatible with the selected deployment providers.

---

## 3. First: Inspect and Understand the Existing Project

Before editing anything:

1. Read the complete project directory structure.
2. Read the existing `agent.md`, `skill.md`, and `design.md`, if present.
3. Read the current README and architecture documentation.
4. Inspect all Next.js pages, layouts, components, and hooks.
5. Inspect the Flask API structure and authentication system.
6. Inspect PostgreSQL models and Alembic migrations.
7. Inspect the existing matching and route-optimization algorithms.
8. Inspect the current customer, delivery partner, and admin workflows.
9. Inspect existing environment variables and deployment configuration.
10. Identify which existing functionality can be reused.

Prepare an internal implementation plan and dependency map.

Then implement the complete changes without stopping for approval between development phases.

Keep the existing application name, repository, and deployment architecture.

---

## 4. Database Reset and New Data Architecture

The current database contains earlier demo data and an outdated operational structure.

I want a fresh operational dataset and a database structure suitable for the redesigned system.

### Data reset instructions

For a **local or explicitly designated disposable development/demo database**:

1. Inspect the existing schema and migrations.
2. Create a backup before destructive operations.
3. Remove outdated demo customers, orders, drivers, routes, batches, assignments, and tracking records.
4. Remove obsolete data relationships that no longer match the new business model.
5. Update the database schema using Alembic migrations.
6. Reinitialize the application with a clean operational state.
7. Bootstrap an administrator securely.
8. Create realistic demo records only when development demo seeding is explicitly enabled.

**Critical safety requirement:** Never automatically delete a production database, real customer records, or a shared database. If the configured database is production or its status is uncertain, preserve all data and prepare the reset procedure separately for explicit authorization.

Never delete migration history casually, expose database credentials, or modify Neon production data without a verified safe reset procedure.

The new system must also work with an entirely empty order database.

Remove hardcoded demo statistics from production dashboards.

### Suggested database entities

Design normalized PostgreSQL models for:

- Users
- UserRoles and Permissions
- ConsumerProfiles
- BusinessProfiles
- Managers
- DeliveryPartners
- Vehicles
- VehicleCapacityProfiles
- DriverAvailability
- DriverDutySessions
- DriverLocationEvents
- ServiceAreas
- Orders
- ParcelDetails
- ReturnRequests
- PickupAddresses
- DeliveryAddresses
- Contacts
- ParcelImages
- OrderStatusHistory
- DeliveryBatches
- BatchOrders
- RoutePlans
- RouteStops
- RouteLegs
- RouteAssignmentHistory
- DriverAssignments
- MatchingSuggestions
- MatchingRejectionReasons
- PickupProofs
- DeliveryProofs
- ProofMedia
- DeliveryExceptions
- Notifications
- IssueReports
- AuditLogs
- AdminSettings

Use foreign keys, appropriate indexes, uniqueness constraints, and transaction-safe assignment logic.

One parcel must never be assigned to two active drivers simultaneously.

---

## 5. New User Roles and Authentication System

There must be **four primary roles**:

1. Consumer
2. Delivery Partner / Driver
3. Manager
4. Administrator

Each role must have its own dashboard, navigation, permissions, and operational workflows.

### 5.1 Consumer Registration

Only consumers may register themselves through the public registration page.

A consumer may be:

- An individual sending a parcel.
- A business owner sending customer orders.
- A merchant requesting product returns.
- A person returning a purchased product.
- A customer using ReTurn's services regularly.

Do not require a separate public business-owner authentication role.

Instead, provide an optional business profile within the consumer account.

During registration, collect:

- Full name
- Email
- Mobile number
- Password
- Confirm password
- Individual or business account preference

For a business profile, optionally collect:

- Business name
- Business category
- Business address
- Contact number
- Business logo
- Pickup address
- Tax or business registration details, when relevant

A business owner logs in as a consumer and gains access to business-friendly shipping features.

The same consumer account may send personal parcels and business parcels.

### 5.2 Driver Account Creation

Drivers cannot sign up publicly.

A driver account can be created by:

- Manager
- Administrator

When creating a driver, capture:

- Full name
- Mobile number
- Email
- Temporary activation credentials
- Vehicle type
- Vehicle registration
- Vehicle weight capacity
- Vehicle volume capacity
- Maximum parcel size
- Service area
- Driver status
- Required identity and vehicle verification information

A driver must activate their account securely and change the temporary password.

Do not email plaintext passwords or store passwords in plaintext.

### 5.3 Manager Account Creation

Only administrators can create manager accounts.

Managers cannot register publicly.

The administrator specifies:

- Manager name
- Email
- Contact number
- Assigned service areas
- Account status
- Permissions

Managers can create and manage drivers within their permitted service areas.

Managers must not create other managers or administrators.

### 5.4 Administrator Account Creation

Administrators can manage accounts for every role.

For security, the initial administrator should be created through a secure bootstrap procedure.

Additional administrators can be created only by an appropriately authorized administrator.

Do not allow public administrator registration.

### Authentication requirements

Implement:

- Secure password hashing
- Secure session cookies
- CSRF protection
- Role-based access control
- Server-side ownership validation
- Login rate limiting
- Account suspension
- Password reset
- Secure logout
- Session expiration
- Audit logging
- Optional MFA for administrative accounts

All permissions must be enforced by the Flask backend, not only by hidden frontend buttons.

---

## 6. Consumer Perspective — Complete Workflow

The consumer dashboard should be simple, premium, and easy to use.

The main services are:

### Service A: Send a Parcel

A consumer or business owner can send a package to another person.

Example:

A clothing business receives an order from a customer.

The business owner logs in to ReTurn, selects **Send Parcel**, and creates a shipping request.

The form must include:

**Sender details**

- Sender name
- Sender phone
- Individual or business profile
- Pickup address
- Pickup location on map
- Pickup contact person

**Recipient details**

- Recipient full name
- Recipient contact number
- Delivery address
- Delivery location on map
- Optional delivery instructions

**Parcel information**

- Parcel name or description
- Parcel category
- Quantity
- Weight
- Dimensions
- Fragile or special handling
- Declared value, if applicable
- Parcel photograph
- Optional business order reference

**Delivery details**

- Pickup date
- Preferred pickup window
- Delivery deadline
- Service notes
- Special requirements

### Parcel photograph

The sender must be able to take or upload a clear photograph of the parcel before handing it over.

Photographing the outside packaging is sufficient.

The sender must never be required to open sealed packaging or expose private contents.

Show an image preview before submission.

For the redesigned workflow, make one exterior parcel photograph part of the normal booking process, with a documented exception process for inaccessible cameras or approved special cases.

### Driver availability

Before confirming an order, the consumer should see realistic service availability.

Examples:

- Pickup service available in this area
- Drivers currently available nearby
- Pickup slot available
- Limited availability
- No driver available for the requested time

Availability must be calculated from actual driver/service-area and schedule data.

Do not invent available drivers or exact pickup times.

The interface may show an estimated pickup window, but it must not promise a driver until the booking is confirmed and assigned.

A consumer must not directly assign a driver.

### After submission

Create a unique order ID.

Display:

- Order received
- Pending manager review
- Matching in progress
- Awaiting assignment
- Driver assigned
- Pickup scheduled
- Picked up
- In transit
- Out for delivery
- Delivered
- Delivery issue

Use statuses consistent with the actual workflow.

Consumers can view their order history, parcel status, driver details when appropriate, and delivery confirmation.

---

## 7. Consumer Perspective — Return a Product

ReTurn must also support reverse logistics.

An individual customer can request a return shipment to an eligible business owner or authorized return destination.

Example:

A customer purchased shoes from a business.

The customer wants to return the shoes.

The customer chooses **Return Product** inside ReTurn.

The request includes:

- Product name
- Original order reference
- Reason for return
- Pickup location
- Sender contact details
- Authorized return destination
- Business or merchant details
- Preferred pickup time
- Parcel weight and dimensions
- Exterior parcel photograph
- Optional return authorization reference

The return parcel may be delivered to:

- The original business owner.
- A designated business address.
- An authorized warehouse.
- A return processing center.

Do not assume all returns go to one central warehouse.

A business owner can also create a return collection request on behalf of a customer, provided the customer has authorized it.

Business returns may require merchant approval or a return authorization before pickup.

**Important:** ReTurn must support normal consumers sending parcels to businesses as well as businesses sending parcels to consumers.

It must not be restricted to e-commerce merchants only.

The pickup and delivery system should support any permitted sender-recipient combination.

---

## 8. Driver Perspective — Complete Delivery Partner System

A driver logs in with an account created by a manager or administrator.

Drivers must have a dedicated mobile-first interface, suitable for use on a phone.

### Driver Dashboard

Display:

- Driver name
- Vehicle information
- Current duty status
- Assigned route
- Assigned batches
- Total parcels assigned
- Completed deliveries
- Remaining deliveries
- Pending pickups
- Failed deliveries
- Vehicle load
- Next recommended stop
- Today's route distance estimate
- Today's activity timeline

### Driver Duty Status

Provide:

- Off Duty
- Available
- On Duty
- On Break
- Busy
- Unavailable

Distinguish between logged-in status and on-duty status.

A driver being logged in must not automatically mean they are available for orders.

### Route Map

When assigned a batch, the driver should see:

- All pickup stops
- All delivery stops
- Recommended stop sequence
- Current location, with permission
- Active route
- Next destination
- Estimated distance
- Estimated time
- Parcel information
- Load remaining

Include navigation links to an external map app where supported.

Do not fake road-navigation results or live GPS positions.

---

## 9. The Most Important Innovation — Dynamic On-Route Order Matching

This is the core feature of ReTurn.

It must work correctly, with real backend logic.

### Example scenario

A driver is assigned a delivery route:

**Barasat → Madhyamgram → Airport → Salt Lake**.

The driver has a bike and is already carrying several parcels.

While the driver is on duty, another customer creates a parcel pickup request in Madhyamgram with a delivery destination near Salt Lake.

The ReTurn system should:

1. Detect the newly submitted order.
2. Identify drivers currently on duty.
3. Check which drivers have an existing route near the new pickup point.
4. Check whether the requested destination can be integrated into the route.
5. Check vehicle capacity.
6. Check existing parcels and commitments.
7. Check delivery deadlines and time windows.
8. Calculate possible route detours.
9. Evaluate the added travel time.
10. Determine whether the driver can perform the pickup and delivery.
11. Generate an explainable matching recommendation.
12. Send the recommendation to the responsible manager.

For example:

**Driver: Arjun**

Current route: Barasat → Salt Lake  
Existing orders: 4  
Vehicle: Bike  
New compatible order: RT-1048  
Additional estimated detour: 1.8 km  
Available vehicle capacity: Sufficient  
Result: Recommended for assignment

### Assignment authority

A matching recommendation is not an automatic assignment.

By default, the manager must approve the new assignment.

The manager should see:

- Driver identity
- Existing assigned parcels
- Current route
- New pickup
- New delivery point
- Additional distance
- Additional time
- Current available capacity
- Proposed updated stop sequence
- Eligibility result
- Clear reasons for compatibility

The manager can:

- Approve assignment
- Reject suggestion
- Select another driver
- Keep the order pending
- Recalculate the proposed route

Once the manager approves, the system must transactionally revalidate the assignment.

Notify the driver of the new task and updated route.

The driver can acknowledge the update. Handle cases where the driver cannot safely accept additional work.

### Rejection cases

Do not recommend or assign a task when:

- Vehicle capacity is exceeded.
- Parcel dimensions are too large.
- Pickup is too far from the active route.
- Delivery deadlines cannot be met.
- Pickup windows are incompatible.
- The driver is off duty.
- The driver is on a break or unavailable.
- The vehicle does not support the parcel type.
- Existing committed deliveries would be delayed beyond allowed limits.
- Handling restrictions conflict.
- The required service area is unsupported.
- The driver has exceeded safe workload limits.

Return clear machine-readable rejection reasons.

Example:

- `vehicle_capacity_exceeded`
- `pickup_window_conflict`
- `driver_not_available`
- `route_detour_too_large`
- `delivery_deadline_conflict`

### Route optimization constraints

The matching engine must enforce:

- Pickup-before-delivery precedence.
- Weight capacity.
- Volume capacity.
- Maximum parcel dimensions.
- Time windows.
- Deadlines.
- Handling restrictions.
- Current vehicle load at each stop.
- Driver availability.
- Service area.
- Existing route commitments.
- Configurable detour thresholds.
- Configurable working-hour limits.

A small group can be optimized using a deterministic, explainable heuristic.

Do not label the engine as AI or machine learning unless a real AI/ML component is implemented.

Use real road-route calculations when available.

When routing services are unavailable, use explicitly labelled estimates and do not present straight-line connectors as road navigation.

---

## 10. Manager Perspective — Complete Operations Control

The Manager Dashboard is one of the most important application surfaces.

Managers are responsible for daily delivery operations within their assigned service areas.

### Manager Dashboard Overview

Display real database-driven statistics:

- Total drivers
- Drivers logged in
- Drivers on duty
- Drivers available
- Drivers busy
- Drivers offline
- New orders today
- Pending orders
- Orders awaiting assignment
- Active delivery batches
- Parcels picked up
- Parcels in transit
- Delivered orders
- Failed deliveries
- Delayed deliveries
- Orders requiring attention

Do not use static random numbers.

### Manager Order Management

Managers can:

- View all orders within their permitted service areas.
- Search by order ID.
- Filter by consumer, business, date, service type, and status.
- View parcel details.
- View pickup and delivery addresses.
- View customer contact details needed for operations.
- Review delivery requirements.
- Approve eligible orders for scheduling.
- Create batches.
- Assign drivers.
- Reassign eligible orders.
- Monitor delays.
- Handle delivery exceptions.
- Review pickup and delivery proof.

### Manual and Smart Batch Creation

Suppose five orders are pending in a particular region.

The manager can select compatible orders and request a batch proposal.

The system must evaluate:

- Pickup proximity
- Destination compatibility
- Delivery time windows
- Vehicle capacity
- Driver service areas
- Parcel weight
- Parcel dimensions
- Deadlines
- Expected route efficiency

The manager can then create a batch and assign it to an appropriate driver.

### Vehicle Capacity Rules

Do not assign:

- Heavy industrial parcels to a bike.
- Parcels larger than the bike's permissible dimensions.
- More weight than the vehicle can carry.
- Too many parcels for its available volume.
- More active deliveries than a driver can reasonably complete.

Use configurable actual vehicle capacity profiles, not arbitrary hardcoded parcel-count rules.

### Driver Management

Managers can:

- Create driver accounts.
- View driver profiles.
- Activate or deactivate drivers.
- Review verification status.
- Assign service areas.
- Review vehicles.
- View driver availability.
- View assigned batches.
- Review active work.
- Review completed deliveries.
- View delivery performance.

They cannot manage drivers outside their authorized scope.

### Driver Tracking

The manager should have a live operations dashboard showing:

- Drivers currently on duty
- Latest reported driver location
- Location update timestamp
- Current route
- Current task
- Next stop
- Completed parcels
- Pending parcels
- Delayed tasks
- Reported incidents
- Vehicle load

A map should show the actual latest available driver locations.

Only collect driver location while the driver is on duty and has granted appropriate permissions.

The UI must clearly distinguish:

- Live recent location
- Stale location
- Tracking unavailable

Never fabricate a moving driver marker.

### Batch Monitoring

For each batch, display:

- Batch ID
- Assigned driver
- Vehicle type
- Order count
- Pickup count
- Delivery count
- Current status
- Stop sequence
- Completed stops
- Remaining stops
- Estimated completion time
- Reported issues

Managers should see the complete progress of a batch.

---

## 11. Proof of Pickup and Proof of Delivery

This is a mandatory operational feature.

A delivery must not be marked successfully delivered without valid proof.

### At Parcel Pickup

Driver opens the assigned parcel and selects **Confirm Pickup**.

The application should capture:

- Order ID
- Driver ID
- Pickup timestamp
- Current GPS coordinates
- Pickup proof image when required by the configured workflow
- Pickup confirmation status

Provide an issue flow if the parcel is missing, damaged, or cannot be collected.

### At Parcel Delivery

Driver reaches the recipient's location.

The driver must click **Capture Delivery Proof**.

The application should:

1. Request camera permission.
2. Open the device camera.
3. Require a fresh photograph of the handed-over parcel or permitted delivery evidence.
4. Request current location permission.
5. Obtain the latest location coordinates.
6. Record the time.
7. Upload the evidence securely.
8. Associate it with the order and authenticated driver.
9. Validate the delivery proof on the server.
10. Mark the order as Delivered only after successful validation.

### Store proof information

- Proof ID
- Order ID
- Driver ID
- Uploaded image reference
- Server-recorded capture event time
- Server receipt time
- Latitude
- Longitude
- Location accuracy
- Proof type
- Proof verification status

Do not rely solely on untrusted image EXIF data or client-provided timestamps.

Require a newly captured image through the application for normal delivery completion; a gallery upload must not silently satisfy this requirement.

Capture the authenticated driver session and verify that the driver is assigned to the order.

### Critical rule

**No valid mandatory delivery proof = No normal Delivered status.**

If camera permission, GPS access, or network connectivity fails:

- Do not falsely mark the parcel delivered.
- Show a clear error and retry path.
- Allow the driver to report a delivery-proof exception.
- Keep the order in a suitable pending-verification status.
- Permit only a separately authorized, audited manager/admin exception process when justified.

Do not let drivers bypass mandatory proof by directly calling an API.

Do not expose customers' private parcel photographs publicly.

---

## 12. Administrator Perspective — Complete Platform Control

Administrators must have a global monitoring and management system.

### Admin Dashboard

Show platform-wide:

- Total consumers
- Business consumers
- Managers
- Drivers
- Active drivers
- Registered vehicles
- Orders today
- Total active orders
- Pending orders
- Active batches
- Completed deliveries
- Failed deliveries
- Delivery exceptions
- Route matching performance
- Estimated distance saved
- Estimated environmental savings
- Service-area performance

### Administrator Permissions

Administrators can:

- View all operational data.
- Manage consumers.
- Manage business accounts.
- Create managers.
- Create drivers.
- Manage all accounts.
- Suspend accounts.
- Review verification documents.
- Manage vehicles.
- Manage service areas.
- Monitor all orders.
- Monitor all batches.
- View all route assignments.
- Review driver locations when authorized.
- Review delivery proof.
- Manage exceptions.
- Configure matching rules.
- Configure vehicle capacity limits.
- View system audit logs.
- View platform analytics.

### Admin Live Operations

Create a map-based operations control center showing:

- Drivers on duty
- Active routes
- Active batches
- New orders
- Pending pickups
- In-transit parcels
- Delivery exceptions

Include useful filters and a detailed activity timeline.

Admin must be able to inspect manager actions and assignments across the platform.

However, unrestricted business access does not mean bypassing security, privacy controls, or audit logging.

---

## 13. Required Application Pages

Implement real, fully connected pages for every major workflow.

### Public and Authentication

1. Landing Page
2. Login
3. Consumer Registration
4. Forgot/Reset Password
5. Account Activation
6. Forbidden / Unauthorized
7. Error / Not Found

### Consumer

8. Consumer Dashboard
9. Send Parcel
10. Return Product
11. Driver/Service Availability
12. Order Confirmation
13. My Orders
14. Order Details
15. Parcel Tracking
16. Order History
17. Business Profile
18. Saved Addresses
19. Notifications
20. Profile and Settings
21. Support and Issues

### Driver

22. Driver Dashboard
23. Assigned Orders
24. Assigned Batches
25. Active Route Map
26. Stop/Order Details
27. Confirm Pickup
28. Capture Delivery Proof
29. Delivery History
30. Duty and Availability
31. Vehicle Profile
32. Report Delivery Issue
33. Driver Notifications

### Manager

34. Manager Dashboard
35. Order Management
36. Pending Assignments
37. Smart Matching Suggestions
38. Batch Creation
39. Batch Details
40. Driver Management
41. Create Driver
42. Live Driver Tracking
43. Route Management
44. Delivery Progress
45. Proof Verification
46. Delivery Issues
47. Reports and Analytics

### Administrator

48. Admin Dashboard
49. Consumer Management
50. Business Account Management
51. Manager Management
52. Driver Management
53. Create Account
54. Vehicle Management
55. All Orders
56. All Batches
57. Global Live Operations
58. Route Monitoring
59. Delivery Proof Audit
60. Service Area Management
61. Matching Configuration
62. Reports and Sustainability
63. Audit Logs
64. Platform Settings

Use shared components and nested layouts where appropriate. Do not duplicate entire pages unnecessarily.

Every listed functional page must have meaningful content, proper authorization, and working navigation.

No decorative buttons with missing functionality.

---

## 14. Order and Batch State Management

Define a reliable order lifecycle.

Suggested order statuses:

- Draft
- Submitted
- Pending Review
- Awaiting Assignment
- Assigned
- Pickup Scheduled
- Pickup Arrived
- Picked Up
- In Transit
- Out for Delivery
- Delivery Proof Pending
- Delivered
- Delivery Failed
- Return in Progress
- Returned
- Cancelled

Use clear rules for valid state transitions.

For instance:

- A parcel cannot be delivered before pickup.
- An unassigned driver cannot confirm delivery.
- A cancelled order cannot be automatically assigned.
- A delivered order cannot return to In Transit without an authorized correction workflow.

Maintain a complete history of every important transition.

Batch states must be maintained separately from individual parcel states.

A batch containing several parcels must not be marked fully completed until its included tasks have reached appropriate terminal states.

---

## 15. Notifications and Real-Time Operational Updates

Implement notifications for important actions.

### Consumer notifications

- Order submitted
- Pickup scheduled
- Driver assigned
- Driver approaching, when real location supports it
- Parcel picked up
- Parcel in transit
- Out for delivery
- Delivered
- Delivery exception

### Driver notifications

- New batch assigned
- Route updated
- New on-route task offered
- Manager instruction
- Pickup reminder
- Delivery exception update

### Manager notifications

- New order received
- Smart matching opportunity
- Driver unavailable
- Delivery delayed
- Proof validation problem
- Batch completed
- Delivery failed

### Admin notifications

- Operational issues
- Account verification requests
- Critical delivery exceptions
- Security-relevant events

Prefer an authenticated event stream or WebSocket implementation for live updates. A reliable polling solution is acceptable if properly implemented.

Do not display fake live events.

---

## 16. Frontend Design — Premium Modern Logistics Platform

Completely improve the existing interface while preserving the ReTurn identity.

The application should look like a polished logistics SaaS platform, not a generic dashboard template.

### Design direction

- Premium enterprise design
- Clean, modern interface
- Large readable typography
- Excellent spacing
- Clear hierarchy
- Minimal visual clutter
- Elegant sidebar navigation
- High-quality tables
- Beautiful map integrations
- Responsive interactions
- Subtle animations
- Distinct status indicators
- Professional analytics cards

### Suggested visual system

Use a design-token-driven system with a recognizable ReTurn visual identity.

Suggested palette:

- Primary: Deep navy `#0D1B2A`
- Brand green: `#10B981`
- Accent teal: `#14B8A6`
- Background: `#F6F8FB`
- Card surface: `#FFFFFF`
- Primary text: `#172033`
- Secondary text: `#64748B`
- Warning: `#F59E0B`
- Error: `#EF4444`

These are suggested defaults; preserve and refine any stronger existing ReTurn brand tokens.

Typography: Geist or Inter.

Support light mode and optionally dark mode.

### Consumer Design

Make the consumer interface intuitive, with prominent actions:

**Send Parcel** and **Return Product**.

Use a polished multi-step booking wizard, map address selection, availability feedback, parcel photo upload, and clear tracking timeline.

### Driver Design

Design mobile-first.

Show large actionable controls:

- Start Duty
- View Route
- Confirm Pickup
- Capture Delivery Proof
- Report Issue
- Complete Stop

The driver should not have to navigate complicated tables while working.

### Manager Design

Create a sophisticated dispatch workspace.

Important UI:

- Map and order queue side by side
- Driver availability panel
- Matching recommendation cards
- Batch creation interface
- Capacity indicators
- Assignment confirmation
- Live delivery progress

### Admin Design

Build a global operations control center with advanced analytics, fleet monitoring, user management, platform configuration, and audit visibility.

All dashboards must have useful loading, empty, error, and success states.

---

## 17. Backend API Requirements

Organize Flask APIs around operational domains.

Suggested routes:

### Authentication

- `/api/v1/auth/*`

### Accounts

- `/api/v1/users/*`
- `/api/v1/business-profiles/*`

### Orders

- `/api/v1/orders/*`
- `/api/v1/returns/*`

### Parcel Media

- `/api/v1/parcel-images/*`
- `/api/v1/delivery-proofs/*`

### Drivers

- `/api/v1/drivers/*`
- `/api/v1/driver-duty/*`
- `/api/v1/driver-locations/*`

### Managers

- `/api/v1/manager/*`

### Batches and Assignments

- `/api/v1/batches/*`
- `/api/v1/assignments/*`

### Matching

- `/api/v1/matching/*`

### Routes

- `/api/v1/routes/*`

### Analytics

- `/api/v1/analytics/*`

### Administration

- `/api/v1/admin/*`

These are architectural guidelines, not instructions to create duplicate endpoints if equivalent working APIs already exist.

Every endpoint must have correct validation, authorization, error handling, and documented behavior.

---

## 18. Security and Privacy Requirements

Treat this application as a real logistics platform.

Implement:

- Role-based authorization
- Resource ownership checks
- Manager service-area scope enforcement
- Secure password storage
- Server-side session validation
- CSRF protection
- Proper CORS configuration
- API rate limiting
- Input validation
- Safe file-upload handling
- Private image storage
- Signed or authenticated media access
- Secure environment variables
- Audit logs for sensitive actions
- Protection against duplicate assignments
- Safe database transactions
- Account activation and suspension rules

### Location privacy

Driver GPS tracking must:

- Require appropriate permissions.
- Operate only for authorized delivery activity.
- Clearly indicate when tracking is active.
- Record timestamps and accuracy where available.
- Stop normal collection when the driver ends their duty.
- Use defined retention limits and access restrictions.

Do not expose precise driver movement to unrelated consumers.

Consumers should only see location details appropriate to their own active delivery.

### Media privacy

Do not expose delivery-proof images through predictable public URLs.

Provide retention and deletion policies.

Do not make recipient photographs mandatory. Proof should focus on the parcel or permitted delivery evidence and avoid unnecessarily photographing people.

---

## 19. Real Database Integration

Every dashboard, table, statistic, and tracking view must load data from the PostgreSQL-backed APIs.

Remove placeholder cards that pretend to show real operations.

The application must handle:

- Empty database
- First registered consumer
- No active drivers
- No available vehicles
- No orders
- One order
- Several orders
- No matching opportunities
- Multiple matching opportunities
- Failed deliveries
- Completed batches

Do not crash because demo records are absent.

Use proper empty states.

Examples:

- "No orders received yet."
- "No drivers currently on duty."
- "No compatible drivers found for this request."
- "No deliveries scheduled for today."

Seeded demonstration data must be clearly distinguishable from production data.

---

## 20. Testing Requirements

Do not finish after the pages compile.

Implement and run meaningful automated tests.

### Authentication tests

- Consumer signup succeeds.
- Public driver signup is rejected.
- Public manager signup is rejected.
- Public admin signup is rejected.
- Admin can create a manager.
- Manager can create a driver.
- Manager cannot create an admin.
- Unauthorized role access is rejected.
- Suspended account cannot perform operations.

### Order tests

- Business consumer creates a parcel request.
- Individual consumer creates a parcel request.
- Customer creates a return.
- Pickup and destination are stored separately.
- Parcel details and photographs are associated correctly.
- Consumers cannot view unrelated private orders.

### Matching tests

- On-route compatible order produces a recommendation.
- Nearby order with impossible destination is rejected.
- Bike capacity overload is rejected.
- Oversized parcels are rejected.
- Deadline violations are rejected.
- Off-duty driver is rejected.
- Existing route commitments remain valid.
- Pickup precedes delivery.
- Concurrent managers cannot duplicate an active assignment.
- Manager approval creates a valid assignment.

### Driver tests

- Driver sees only authorized assigned tasks.
- Driver starts duty.
- Driver receives route update.
- Driver records pickup.
- Driver cannot deliver before pickup.
- Driver cannot complete another driver's order.
- Driver delivery proof requires valid image and location evidence.
- Missing mandatory proof prevents normal delivery completion.
- Valid delivery proof updates order status.
- Manager can view delivery progress.
- Duty status correctly controls live location collection.

### Database tests

- Migrations apply successfully.
- Clean empty database initializes successfully.
- Referential integrity is maintained.
- Duplicate active assignment is prevented.
- Order history is preserved.
- Demo seeding is not performed unintentionally in production.

### Frontend tests

- All navigation works.
- Role-based layouts load correctly.
- Booking forms validate inputs.
- File upload works.
- Manager batch creation works.
- Driver proof capture workflow works.
- Empty states display correctly.
- Responsive views work on mobile and desktop.

Use real API integration tests, not just mock data tests.

---

## 21. End-to-End Demonstration Scenario

Create an optional fictional demonstration scenario.

### Scenario A — Business Order

A business owner registers as a consumer.

They create an order for a recipient.

The order enters the manager's queue.

The manager identifies an appropriate driver and assigns it.

The driver picks up and delivers the parcel.

The driver captures mandatory delivery proof.

The consumer sees Delivered only after successful verification.

### Scenario B — Dynamic Route Matching

Driver Arjun is already delivering three parcels on a route.

A new parcel pickup request appears near the driver's route.

The system checks time, vehicle capacity, distance, destination compatibility, and existing commitments.

The manager receives a matching suggestion.

The manager approves it.

The driver receives an updated route.

The new parcel is collected and delivered.

The customer can track the order.

### Scenario C — Product Return

A customer creates a return request to an authorized business destination.

The manager assigns it to a compatible driver or combines it into an existing route.

The driver collects the item and delivers it to the authorized return address.

The return has its own tracking events and completion evidence.

### Scenario D — Capacity Rejection

A heavy parcel request arrives.

The system evaluates a bike driver.

The request is rejected for that driver because of insufficient capacity.

The manager sees the rejection explanation and selects an eligible vehicle.

### Scenario E — Delivery Proof Failure

A driver tries to mark a parcel Delivered without submitting the required photograph and location evidence.

The backend rejects normal completion.

The application displays the required corrective action.

The delivery remains pending verification.

---

## 22. Deployment Compatibility

The existing project uses:

- GitHub for source control
- Vercel for the Next.js frontend
- Render for the Flask API
- Neon for PostgreSQL

Preserve compatibility.

Review and update:

- `render.yaml`
- `vercel.json`, if present
- `docker-compose.yml`
- Frontend Dockerfile
- Backend Dockerfile
- Environment templates
- Database migrations
- API proxy configuration
- Health endpoints

Do not break the existing deployment pipeline.

Make sure authentication cookies, secure sessions, CSRF behavior, media uploads, CORS, and proxy requests work with the deployed architecture.

Do not hardcode production credentials.

Provide production-safe configuration for image storage and location updates.

---

## 23. Implementation Priorities

Implement the work in this logical order:

### Phase 1 — Architecture and Database

- Inspect existing code
- Design updated models
- Prepare safe data-reset process
- Create migrations
- Implement core domain services

### Phase 2 — Authentication and Roles

- Consumer signup
- Admin provisioning
- Manager provisioning
- Driver provisioning
- RBAC

### Phase 3 — Consumer Workflows

- Send parcel
- Return parcel
- Addresses
- Parcel images
- Availability
- Order tracking

### Phase 4 — Driver Workflows

- Duty management
- Vehicle capacity
- Assigned orders
- Route navigation
- Pickup confirmation
- Delivery proof

### Phase 5 — Manager Dispatch

- Driver monitoring
- Order queue
- Batch creation
- Manual assignment
- Route-aware recommendations
- Dynamic route reassignment

### Phase 6 — Administration

- Global operational monitoring
- Account management
- Delivery audits
- Settings
- Analytics

### Phase 7 — Testing and Deployment

- Backend tests
- Frontend tests
- Integration tests
- Security checks
- Production build
- Deployment verification

These phases are an implementation order, not permission checkpoints.

Complete the full implementation before declaring the project finished.

---

## 24. Strict Development Rules

1. Do not rename ReTurn.
2. Do not create a new unrelated application.
3. Reuse the existing Next.js and Flask architecture.
4. Keep PostgreSQL as the database.
5. Do not deliver only a dashboard UI.
6. Do not use fake functionality for core workflows.
7. Do not hardcode live operational statistics.
8. Do not assign orders without server-side capacity and feasibility checks.
9. Do not let consumers manually assign delivery partners.
10. Do not permit public signup for drivers, managers, or admins.
11. Do not mark a delivery complete without mandatory proof or an explicitly audited exception.
12. Do not invent GPS coordinates or driver movement.
13. Do not use a simple nearby-distance check as the entire matching algorithm.
14. Do not destroy production data automatically.
15. Do not expose private customer information between unrelated accounts.
16. Do not use insecure public demo credentials in production.
17. Do not leave buttons without meaningful working behavior.
18. Do not stop after creating database models or visual components.
19. Do not claim tests passed unless they were executed.
20. Do not claim successful deployment without deployment verification.

---

## 25. Final Completion Requirements

Before reporting completion:

- Confirm consumer registration works.
- Confirm role provisioning works.
- Confirm real PostgreSQL integration works.
- Confirm the Send Parcel workflow works.
- Confirm the Return Product workflow works.
- Confirm driver availability works.
- Confirm manager batch assignment works.
- Confirm vehicle capacity enforcement works.
- Confirm dynamic on-route matching works.
- Confirm driver route updates work.
- Confirm delivery proof capture works.
- Confirm delivery cannot be completed without required proof.
- Confirm manager live monitoring works with genuinely available tracking data.
- Confirm admin can monitor the platform within the defined permissions.
- Confirm updated Next.js production build succeeds.
- Confirm Flask tests pass.
- Confirm migrations apply.
- Confirm deployment configuration is valid.

Update the project's README and architecture documentation.

Provide an implementation summary containing:

1. Features completed.
2. Existing functionality modified.
3. Database migrations created.
4. Test results and commands executed.
5. Configuration required from me.
6. Known limitations.
7. Exact local run commands.
8. Exact production deployment instructions.

If any integration requires external credentials, implement the real integration boundary, document the necessary configuration, and state clearly what cannot be exercised without those credentials.

Do not represent unfinished integrations as working features.

---

# FINAL INSTRUCTION

**Transform ReTurn into a complete, functional, modern logistics operating system for consumers, e-commerce businesses, delivery partners, managers, and administrators.**

The project must support two-way parcel movement: ordinary deliveries and product returns.

Its main innovation is that a driver already travelling along an active route can be identified as a suitable candidate for another compatible delivery or pickup, without compromising existing orders, vehicle capacity, or deadlines.

Managers control dispatch and assignment decisions.

Drivers perform deliveries and must provide verifiable delivery proof.

Consumers can create shipments and returns and monitor their parcels.

Administrators control and monitor the complete platform.

**Implement the actual end-to-end system in my existing ReTurn repository. Do not stop at planning, scaffolding, design mockups, or partial implementation.**

Start by inspecting the existing repository and proceed through implementation, migrations, integration, testing, and documentation.
