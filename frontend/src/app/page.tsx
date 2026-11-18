import {
  ArrowRight,
  Boxes,
  CalendarClock,
  CheckCircle2,
  Clock3,
  Leaf,
  MapPin,
  PackageCheck,
  Route,
  ShieldCheck,
  Sparkles,
  Truck,
} from "lucide-react";
import Link from "next/link";

import { Brand, RouteMark } from "@/components/Brand";
import { palette } from "@/lib/design-tokens";
import { getMe } from "@/lib/server";
import type { AuthMe } from "@/lib/types";
import { homeFor } from "@/lib/roles";

const CHECKS = [
  {
    icon: Clock3,
    title: "Pickup windows",
    body: "Every stop must fit inside the consumer's stated collection window — no planned lateness.",
  },
  {
    icon: CalendarClock,
    title: "Delivery deadlines",
    body: "Arrival estimates are simulated stop by stop against the recipient's deadline.",
  },
  {
    icon: Boxes,
    title: "Capacity at every stop",
    body: "Weight and volume are checked after each pickup and drop-off, not just as a static sum.",
  },
  {
    icon: MapPin,
    title: "Real destinations",
    body: "Return hubs and recipient addresses stay exactly as authorised. A group never merges them.",
  },
  {
    icon: ShieldCheck,
    title: "Handling & service area",
    body: "Fragile and restricted items are matched only to vehicles and areas that can legally take them.",
  },
  {
    icon: Leaf,
    title: "A genuine benefit",
    body: "A group is proposed only if the estimated shared distance beats separate trips by a configured margin.",
  },
];

const PROCESS = [
  {
    title: "Create",
    body: "A consumer submits a product return to an authorised hub, or a parcel to a recipient's own address.",
    icon: PackageCheck,
  },
  {
    title: "Coordinate",
    body: "ReTurn checks windows, capacity, handling and destinations, then searches for a feasible shared itinerary.",
    icon: Route,
  },
  {
    title: "Execute",
    body: "An assigned, verified driver follows the ordered stops and updates each parcel separately.",
    icon: Truck,
  },
  {
    title: "Track",
    body: "Consumers see their own parcel-level timeline. Managers and admins see the plan, proof and audit trail.",
    icon: CheckCircle2,
  },
];

export default async function LandingPage() {
  let me: AuthMe | null = null;
  try {
    me = await getMe();
  } catch {
    // The public landing page must still render while the API is unreachable
    // (for example during a free-tier cold start).
  }
  const startHref = me ? homeFor(me.user.role) : "/auth";
  const signInHref = me ? homeFor(me.user.role) : "/auth";

  return (
    <div className="min-h-screen">
      <header className="border-b bg-canvas">
        <div className="container-page flex h-[76px] items-center justify-between gap-4">
          <Brand />
          <nav className="hidden items-center gap-6 text-sm text-muted md:flex" aria-label="Landing">
            <a href="#how-it-works" className="hover:text-ink">How it works</a>
            <a href="#services" className="hover:text-ink">Services</a>
            <a href="#checks" className="hover:text-ink">What we check</a>
            <a href="#impact" className="hover:text-ink">Impact</a>
          </nav>
          <div className="flex items-center gap-2">
            <Link href={signInHref} className="btn btn-ghost btn-sm">
              {me ? "Go to dashboard" : "Log in"}
            </Link>
            <Link href={startHref} className="btn btn-primary btn-sm">
              Get started
            </Link>
          </div>
        </div>
      </header>

      <section className="on-dark relative overflow-hidden bg-inverse text-white">
        <div className="glow-sage pointer-events-none absolute -right-20 -top-28 h-[560px] w-[560px] rounded-full" aria-hidden="true" />
        <div className="container-page relative grid gap-12 py-14 lg:grid-cols-[1.02fr_1fr] lg:items-center lg:py-20">
          <div className="animate-fade-up">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-2xs font-medium text-white">
              <Sparkles size={13} aria-hidden />
              Smart reverse delivery & shared logistics
            </div>
            <h1 className="mt-6 text-xl leading-[1.04] tracking-[-0.03em] sm:text-2xl">
              Fewer trips.
              <br />
              Smarter deliveries.
            </h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-white/70">
              ReTurn combines compatible e-commerce returns and ordinary parcels into one feasible multi-stop route —
              only when windows, capacity, handling and destinations genuinely allow it. One route. Multiple deliveries.
              Less waste.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href={startHref} className="btn btn-primary">
                Send a parcel <ArrowRight size={16} aria-hidden />
              </Link>
              <Link href={startHref} className="btn border border-white/20 bg-white/5 text-white hover:bg-white/10">
                Return a product
              </Link>
            </div>
            <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-white/65">
              <span className="inline-flex items-center gap-1.5">
                <ShieldCheck size={14} className="text-white" aria-hidden /> Verified drivers only
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Route size={14} className="text-white" aria-hidden /> Explainable, rule-based matching
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Leaf size={14} className="text-white" aria-hidden /> Estimated, never invented, savings
              </span>
            </div>
          </div>

          <div className="relative">
            <div className="rounded-card border border-white/10 bg-inverse p-4 shadow-floating sm:p-5">
              <div className="flex items-center justify-between gap-3">
                <p className="text-2xs font-medium uppercase tracking-[0.2em] text-white/60">Illustrative neighbourhood plan</p>
                <span className="rounded-full bg-white/15 px-2.5 py-1 text-2xs font-semibold text-white">
                  Illustrative scenario
                </span>
              </div>
              <NeighbourhoodIllustration />
              <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-control border border-white/10 bg-white/[0.04] px-3.5 py-3">
                <div>
                  <p className="text-sm font-semibold">3 requests · 1 coordinated batch</p>
                  <p className="text-2xs text-white/65">Two authorised return hubs and one recipient address preserved</p>
                </div>
                <span className="chip border-white/25 bg-white/10 text-white">Feasibility required</span>
              </div>
            </div>
            <p className="mt-3 text-center text-2xs leading-4 text-white/65">
              Fictional demonstration data. Route geometry is illustrative; savings shown by the product are modelled estimates.
            </p>
          </div>
        </div>
      </section>

      <section id="services" className="container-page py-16">
        <div className="mx-auto max-w-2xl text-center">
          <p className="eyebrow">Two services, one coordination layer</p>
          <h2 className="mt-2 text-lg leading-tight sm:text-2xl">Start with what you actually need</h2>
          <p className="mt-3 text-sm leading-6 text-muted">
            A return and a normal parcel are different journeys. ReTurn keeps that distinction while looking for a
            sensible way to share the road.
          </p>
        </div>
        <div className="mt-8 grid gap-5 md:grid-cols-2">
          <ServiceCard
            tone="return"
            icon={<PackageCheck size={22} aria-hidden />}
            title="Return a product"
            body="Choose the authorised return destination, add your return reference and tell us when the parcel can be collected."
            points={[
              "Authorised return hub stays exactly as provided",
              "Parcel weight, size and handling captured",
              "Pickup window and delivery deadline respected",
            ]}
            href={startHref}
            cta="Return a product"
          />
          <ServiceCard
            tone="parcel"
            icon={<Truck size={22} aria-hidden />}
            title="Send a parcel"
            body="Send something to a recipient's own address. ReTurn may group it with another compatible journey nearby."
            points={[
              "Recipient address and contact captured privately",
              "Weight, volume and handling checked against vehicles",
              "One shared route, independent parcel tracking",
            ]}
            href={startHref}
            cta="Send a parcel"
          />
        </div>
      </section>

      <section id="checks" className="border-y bg-surface-muted py-16">
        <div className="container-page">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="eyebrow">Compatibility, not proximity</p>
              <h2 className="mt-2 text-lg sm:text-xl">What ReTurn checks before grouping</h2>
            </div>
            <p className="max-w-md text-sm leading-6 text-muted">
              Nearby does not always mean compatible. Every proposed group must pass all six checks and beat the
              separate-trip baseline.
            </p>
          </div>
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {CHECKS.map((check) => (
              <div key={check.title} className="card p-5">
                <span className="flex h-10 w-10 items-center justify-center rounded-control bg-accent-soft text-accent-strong">
                  <check.icon size={19} aria-hidden />
                </span>
                <h3 className="mt-4 text-base font-semibold">{check.title}</h3>
                <p className="mt-1 text-sm leading-6 text-muted">{check.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="how-it-works" className="container-page py-16">
        <div className="mx-auto max-w-2xl text-center">
          <p className="eyebrow">The honest workflow</p>
          <h2 className="mt-2 text-lg sm:text-2xl">Create → coordinate → execute → track</h2>
          <p className="mt-3 text-sm leading-6 text-muted">
            No magic dispatch, no fabricated live tracking. A real manager reviews feasibility and an assigned verified driver
            executes each stop with proof.
          </p>
        </div>
        <div className="relative mt-10 grid gap-4 md:grid-cols-4">
          <div className="absolute left-8 right-8 top-9 hidden border-t border-dashed border-line-strong md:block" aria-hidden="true" />
          {PROCESS.map((step, index) => (
            <div key={step.title} className="relative card p-5">
              <div className="flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-sm font-semibold text-ink-deep">
                  {index + 1}
                </span>
                <step.icon size={18} className="text-accent-strong" aria-hidden />
              </div>
              <h3 className="mt-4 text-base font-semibold">{step.title}</h3>
              <p className="mt-1 text-sm leading-6 text-muted">{step.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="impact" className="on-dark bg-inverse py-16 text-white">
        <div className="container-page grid gap-10 lg:grid-cols-[1fr_1.05fr] lg:items-center">
          <div>
            <p className="text-2xs font-semibold uppercase tracking-[0.18em] text-primary">Estimated, with assumptions</p>
            <h2 className="mt-3 text-lg leading-tight sm:text-2xl">
              Transparent impact — not eco theatre
            </h2>
            <p className="mt-3 max-w-xl text-sm leading-6 text-white/65">
              ReTurn compares a defined separate-trip baseline with the planned shared route on the same distance basis.
              Fuel and CO₂e figures use configurable factors and are labelled estimates. We never claim measured
              emissions, live courier GPS, or that a specific number of vehicles was definitely removed.
            </p>
          </div>
          <div className="rounded-card border border-white/10 bg-white/[0.04] p-5">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-control border border-white/10 bg-white/[0.03] p-4">
                <p className="text-2xs uppercase tracking-wide text-white/60">Separate-trip baseline</p>
                <p className="mono mt-2 text-lg font-medium">Modelled</p>
                <p className="mt-1 text-2xs text-white/65">One direct pickup → destination per request</p>
              </div>
              <div className="rounded-control border border-white/25 bg-white/10 p-4">
                <p className="text-2xs uppercase tracking-wide text-white/70">Shared plan</p>
                <p className="mono mt-2 text-lg font-medium text-white">Modelled</p>
                <p className="mt-1 text-2xs text-white/70">Same stops, same estimation basis</p>
              </div>
            </div>
            <ul className="mt-4 space-y-2 text-xs leading-5 text-white/60">
              <li>• “Estimated distance saved” appears only when the shared route is shorter.</li>
              <li>• Negative savings are never rounded up into a positive claim.</li>
              <li>• Road routing is labelled when OSRM is reachable; estimated fallbacks are labelled too.</li>
              <li>• Admin reports show the factors and methodology behind every total.</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="container-page py-16">
        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-4">
          {[
            { title: "Consumers", body: "Send a parcel or return a product, follow a parcel-level timeline, cancel while allowed and report an issue.", icon: PackageCheck },
            { title: "Drivers", body: "Manage duty and vehicle capacity, accept assigned work and complete every stop with proof.", icon: Truck },
            { title: "Managers", body: "Review orders, plan batches, approve explainable route matches and verify delivery proof.", icon: Route },
            { title: "Administrators", body: "Provision accounts, manage areas and fleet, audit proof and tune matching rules platform-wide.", icon: ShieldCheck },
          ].map((role) => (
            <div key={role.title} className="card card-pad">
              <role.icon size={20} className="text-accent-strong" aria-hidden />
              <h3 className="mt-3 text-base font-semibold">{role.title}</h3>
              <p className="mt-1 text-sm leading-6 text-muted">{role.body}</p>
            </div>
          ))}
        </div>
        <div className="panel mt-10 flex flex-col items-center justify-between gap-4 rounded-card border px-6 py-6 sm:flex-row">
          <div className="flex items-center gap-3">
            <RouteMark className="h-10 w-10 text-accent-strong" />
            <div>
              <p className="font-display text-base font-semibold">Ready to see a real shared route?</p>
              <p className="text-sm text-muted">Sign in with a demo role and walk the full workflow.</p>
            </div>
          </div>
          <Link href={startHref} className="btn btn-primary">
            Open ReTurn <ArrowRight size={16} aria-hidden />
          </Link>
        </div>
      </section>

      <footer className="border-t">
        <div className="container-page grid gap-8 py-10 md:grid-cols-[1.4fr_1fr_1fr]">
          <div>
            <Brand />
            <p className="mt-3 max-w-sm text-sm leading-6 text-muted">
              A coordination and constrained route-planning demonstration. ReTurn does not own or operate courier
              vehicles, and does not claim trained AI or measured environmental savings.
            </p>
          </div>
          <div className="text-sm">
            <p className="font-semibold">Explore</p>
            <ul className="mt-2 space-y-1.5 text-muted">
              <li><a href="#how-it-works" className="hover:text-ink">How it works</a></li>
              <li><a href="#checks" className="hover:text-ink">What we check</a></li>
              <li><a href="#impact" className="hover:text-ink">Estimated impact</a></li>
              <li><Link href="/auth" className="hover:text-ink">Sign in</Link></li>
            </ul>
          </div>
          <div className="text-sm">
            <p className="font-semibold">Scope & data</p>
            <ul className="mt-2 space-y-1.5 text-muted">
              <li>Demo data is fictional</li>
              <li>Map data © OpenStreetMap contributors</li>
              <li>Road routing by OSRM when available</li>
              <li>All savings are modelled estimates</li>
            </ul>
          </div>
        </div>
        <div className="border-t">
          <div className="container-page flex flex-col items-start justify-between gap-2 py-4 text-2xs text-muted sm:flex-row sm:items-center">
            <p>© {new Date().getFullYear()} ReTurn. One Route. Multiple Deliveries. Less Waste.</p>
            <p>Built as a hackathon demonstration of feasible shared logistics.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

function ServiceCard({
  title,
  body,
  points,
  href,
  cta,
  icon,
  tone,
}: {
  title: string;
  body: string;
  points: string[];
  href: string;
  cta: string;
  icon: React.ReactNode;
  tone: "return" | "parcel";
}) {
  const isReturn = tone === "return";
  return (
    <div className={`card card-pad border-t-4 ${isReturn ? "border-t-accent" : "border-t-blue"}`}>
      <div className="flex items-start justify-between gap-3">
        <span className={`flex h-11 w-11 items-center justify-center rounded-control ${isReturn ? "bg-accent-soft text-accent-strong" : "bg-blue-soft text-blue-ink"}`}>
          {icon}
        </span>
        <span className={`chip ${isReturn ? "chip-teal" : "chip-blue"}`}>{isReturn ? "Return lane" : "Parcel lane"}</span>
      </div>
      <h3 className="mt-4 text-lg">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-muted">{body}</p>
      <ul className="mt-4 space-y-2 text-sm leading-5">
        {points.map((point) => (
          <li key={point} className="flex gap-2">
            <CheckCircle2 size={15} className={`mt-0.5 shrink-0 ${isReturn ? "text-accent-strong" : "text-blue"}`} aria-hidden />
            {point}
          </li>
        ))}
      </ul>
      <Link href={href} className={`btn mt-5 w-full ${isReturn ? "btn-primary" : "btn-secondary"}`}>
        {cta} <ArrowRight size={15} aria-hidden />
      </Link>
    </div>
  );
}

function NeighbourhoodIllustration() {
  return (
    <svg viewBox="0 0 520 360" className="mt-4 w-full" role="img" aria-label="Illustrative neighbourhood map with three pickups converging into one multi-stop route">
      <defs>
        <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
          <path d="M32 0H0V32" fill="none" stroke="rgba(199,210,172,0.08)" strokeWidth="1" />
        </pattern>
        <linearGradient id="routeFade" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor={palette.accent} />
          <stop offset="100%" stopColor={palette.surface} />
        </linearGradient>
      </defs>
      <rect width="520" height="360" rx="18" fill={palette.base} />
      <rect width="520" height="360" rx="18" fill="url(#grid)" />
      <path d="M-10 250 C 90 240, 120 190, 200 200 S 330 250, 540 220" fill="none" stroke="rgba(255,255,255,0.10)" strokeWidth="20" />
      <path d="M120 -10 C 140 70, 90 130, 120 220 S 110 310, 140 380" fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="14" />
      <path d="M330 -10 C 320 80, 380 150, 360 230 S 380 320, 370 380" fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="12" />
      <path d="M55 300 C 110 280, 150 240, 210 230 S 300 180, 350 165 S 430 120, 470 95" fill="none" stroke="rgba(199,210,172,0.18)" strokeWidth="26" strokeLinecap="round" />
      <path
        d="M92 270 C 130 262, 140 224, 190 212 S 268 176, 318 160 S 378 120, 430 92"
        fill="none"
        stroke="url(#routeFade)"
        strokeWidth="4"
        strokeLinecap="round"
        strokeDasharray="10 7"
        className="route-thread-path"
      />
      <g>
        <circle cx="92" cy="270" r="16" fill={palette.surface} />
        <circle cx="92" cy="270" r="6" fill={palette.ink} />
        <text x="68" y="310" fill={palette.surface} fontSize="11" fontFamily="Saans, Inter, sans-serif">Rahul · return pickup</text>
      </g>
      <g>
        <circle cx="190" cy="212" r="14" fill={palette.ink3} />
        <circle cx="190" cy="212" r="5" fill={palette.ink} />
        <text x="150" y="190" fill={palette.surface} fontSize="11" fontFamily="Saans, Inter, sans-serif">Priya · parcel pickup</text>
      </g>
      <g>
        <circle cx="318" cy="160" r="14" fill={palette.ink} />
        <circle cx="318" cy="160" r="5" fill={palette.base} />
        <text x="288" y="138" fill={palette.surface} fontSize="11" fontFamily="Saans, Inter, sans-serif">Amit · return pickup</text>
      </g>
      <g>
        <rect x="422" y="84" width="18" height="18" rx="5" fill={palette.ink} stroke={palette.surface} strokeWidth="2" />
        <text x="370" y="74" fill={palette.onBase} fontSize="10" fontFamily="Saans, Inter, sans-serif">Salt Lake recipient</text>
      </g>
      <g>
        <rect x="48" y="230" width="17" height="17" rx="5" fill={palette.accent} stroke={palette.surface} strokeWidth="2" />
        <text x="18" y="222" fill={palette.onBase} fontSize="10" fontFamily="Saans, Inter, sans-serif">Authorised hub</text>
      </g>
      <g>
        <rect x="248" y="104" width="17" height="17" rx="5" fill={palette.accent} stroke={palette.surface} strokeWidth="2" />
        <text x="208" y="96" fill={palette.onBase} fontSize="10" fontFamily="Saans, Inter, sans-serif">Authorised hub</text>
      </g>
      <text x="24" y="34" fill={palette.surface} fontSize="10" fontFamily="Saans Semi Mono, ui-monospace, monospace" letterSpacing="1.6">ONE SHARED ROUTE · 6 STOPS</text>
    </svg>
  );
}
