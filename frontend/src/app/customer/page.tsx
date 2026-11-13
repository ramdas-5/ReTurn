import {
  ArrowLeftRight,
  ArrowRight,
  CheckCircle2,
  Clock3,
  MapPin,
  Package,
  PackageOpen,
  Route,
  Truck,
} from "lucide-react";
import Link from "next/link";

import { Callout, EmptyState, PageHeader, StatCard } from "@/components/ui";
import { StatusBadge } from "@/components/Status";
import { formatDateTime, formatWindow, isActiveRequest, serviceLabel } from "@/lib/format";
import { requireUser, serverFetchList } from "@/lib/server";
import type { DeliveryRequest } from "@/lib/types";

export const metadata = { title: "Overview" };

export default async function CustomerDashboard() {
  const me = await requireUser("customer");
  const { data: requests } = await serverFetchList<DeliveryRequest>("/requests?per_page=50");
  const active = requests.filter((request) => isActiveRequest(request.status));
  const pending = requests.filter((request) => request.status === "pending_matching");
  const completed = requests.filter((request) => request.status === "completed");
  const recent = requests.slice(0, 4);
  const nextAction = active[0];
  const firstName = me.user.name.split(" ")[0];

  return (
    <div>
      <PageHeader
        eyebrow="Customer overview"
        title={`Hello, ${firstName}`}
        description="Create a return or send a parcel, then follow each parcel's own journey. ReTurn groups requests only when a shared route is genuinely feasible."
        actions={
          <>
            <Link href="/customer/returns/new" className="btn btn-primary">
              <ArrowLeftRight size={16} aria-hidden /> Return a product
            </Link>
            <Link href="/customer/parcels/new" className="btn btn-secondary">
              <Truck size={16} aria-hidden /> Send a parcel
            </Link>
          </>
        }
      />

      {nextAction ? (
        <section className="card mb-6 overflow-hidden">
          <div className="grid gap-0 md:grid-cols-[1.35fr_1fr]">
            <div className="p-5 sm:p-6">
              <div className="flex flex-wrap items-center gap-2">
                <span className="eyebrow">Your nearest action</span>
                <StatusBadge status={nextAction.status} />
              </div>
              <h2 className="mt-2 text-[22px] font-bold leading-snug">
                {serviceLabel(nextAction.type)} · <span className="mono text-[17px]">{nextAction.code}</span>
              </h2>
              <p className="mt-2 max-w-xl text-sm leading-6 text-muted">{nextAction.next_step}</p>
              <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-[12px] text-muted">
                <span className="inline-flex items-center gap-1.5">
                  <Clock3 size={14} aria-hidden /> {formatWindow(nextAction.pickup_window_start, nextAction.pickup_window_end)}
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <MapPin size={14} aria-hidden /> {nextAction.pickup.area}
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <Package size={14} aria-hidden /> {nextAction.parcel.description}
                </span>
              </div>
              <div className="mt-5 flex flex-wrap gap-2">
                <Link href={`/customer/requests/${nextAction.id}`} className="btn btn-primary">
                  Track this request <ArrowRight size={15} aria-hidden />
                </Link>
                <Link href="/customer/requests" className="btn btn-secondary">
                  All requests
                </Link>
              </div>
            </div>
            <div className="relative min-h-[190px] bg-ink p-5 text-white sm:p-6">
              <div className="absolute inset-0 opacity-25" aria-hidden="true">
                <svg viewBox="0 0 360 220" className="h-full w-full">
                  <path d="M30 170 C 90 170, 90 90, 170 90 S 250 150, 330 80" fill="none" stroke="#CBF08C" strokeWidth="2" strokeDasharray="7 6" />
                  <circle cx="30" cy="170" r="8" fill="#CBF08C" />
                  <rect x="322" y="72" width="16" height="16" rx="4" fill="#67DDB0" />
                </svg>
              </div>
              <div className="relative">
                <p className="text-[11px] uppercase tracking-[0.16em] text-lime">Journey</p>
                <p className="mt-2 text-sm font-medium">{nextAction.pickup.label}</p>
                <p className="mt-1 text-[11px] text-white/50">Pickup</p>
                <div className="my-3 h-px w-16 bg-white/20" />
                <p className="text-sm font-medium">
                  {nextAction.type === "return"
                    ? nextAction.return_detail?.authorized_hub_name ?? nextAction.destination.label
                    : nextAction.recipient?.name
                      ? `${nextAction.destination.area} · ${nextAction.recipient.name}`
                      : nextAction.destination.label}
                </p>
                <p className="mt-1 text-[11px] text-white/50">
                  {nextAction.type === "return" ? "Authorised return destination" : "Recipient delivery address"}
                </p>
                {nextAction.batch ? (
                  <p className="mt-4 inline-flex rounded-full border border-white/15 bg-white/5 px-2.5 py-1 text-[10px] text-white/70">
                    {nextAction.batch.code} · <span className="capitalize">{nextAction.batch.status.replaceAll("_", " ")}</span>
                  </p>
                ) : null}
              </div>
            </div>
          </div>
        </section>
      ) : (
        <div className="mb-6">
          <Callout tone="info" title="Nothing is moving right now">
            You have no active requests. Start a return or send a parcel and ReTurn will check compatibility when a
            matching run happens. Grouping is never guaranteed.
          </Callout>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Active requests" value={active.length} hint="Pending, batched or on route" icon={<Route size={17} aria-hidden />} tone="accent" />
        <StatCard label="Waiting for match" value={pending.length} hint="Nearby is not automatically compatible" icon={<Clock3 size={17} aria-hidden />} />
        <StatCard label="Completed" value={completed.length} hint="Delivered requests in your history" icon={<CheckCircle2 size={17} aria-hidden />} tone="blue" />
        <StatCard label="Total requests" value={requests.length} hint="All time" icon={<PackageOpen size={17} aria-hidden />} />
      </div>

      <section className="mt-8">
        <div className="mb-4 flex items-end justify-between gap-3">
          <div>
            <h2 className="section-title">Start a new journey</h2>
            <p className="mt-1 text-sm text-muted">Two services, kept distinct all the way through.</p>
          </div>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <Link
            href="/customer/returns/new"
            className="group card overflow-hidden border-t-4 border-t-accent p-5 transition hover:border-accent sm:p-6"
          >
            <div className="flex items-start justify-between gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-control bg-accent-soft text-accent-strong">
                <ArrowLeftRight size={20} aria-hidden />
              </span>
              <span className="chip chip-teal">Return lane</span>
            </div>
            <h3 className="mt-4 text-xl font-bold">Return a product</h3>
            <p className="mt-1 text-sm leading-6 text-muted">
              Send an item back to the authorised returns destination for that purchase. Capture the return reference so
              the journey stays traceable.
            </p>
            <span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-accent">
              Create a return <ArrowRight size={15} className="transition group-hover:translate-x-0.5" aria-hidden />
            </span>
          </Link>
          <Link
            href="/customer/parcels/new"
            className="group card overflow-hidden border-t-4 border-t-[#2c6ca2] p-5 transition hover:border-[#2c6ca2] sm:p-6"
          >
            <div className="flex items-start justify-between gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-control bg-blue-soft text-[#1d5580]">
                <Truck size={20} aria-hidden />
              </span>
              <span className="chip chip-blue">Parcel lane</span>
            </div>
            <h3 className="mt-4 text-xl font-bold">Send a parcel</h3>
            <p className="mt-1 text-sm leading-6 text-muted">
              Deliver to a recipient&apos;s own address. ReTurn may share the route with another compatible journey
              nearby, but the destination never changes.
            </p>
            <span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-[#2c6ca2]">
              Send a parcel <ArrowRight size={15} className="transition group-hover:translate-x-0.5" aria-hidden />
            </span>
          </Link>
        </div>
      </section>

      <section className="mt-8">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="section-title">Recent requests</h2>
            <p className="mt-1 text-sm text-muted">Every parcel keeps its own status and tracking history.</p>
          </div>
          <Link href="/customer/requests" className="btn btn-secondary btn-sm">
            View all
          </Link>
        </div>
        {recent.length === 0 ? (
          <EmptyState
            icon={<PackageOpen size={20} aria-hidden />}
            title="Your first request starts here"
            description="Your parcel journey will appear here after you submit a request. Returns go to their authorised hub; parcels go to the recipient."
            action={
              <Link href="/customer/returns/new" className="btn btn-primary btn-sm">
                Create your first return
              </Link>
            }
          />
        ) : (
          <ul className="space-y-3">
            {recent.map((request) => (
              <li key={request.id} className="card flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between sm:gap-5">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="mono text-[12px] font-medium">{request.code}</span>
                    <StatusBadge status={request.status} />
                  </div>
                  <p className="mt-1 text-sm">
                    <span className="font-medium">{request.pickup.area}</span>
                    <span className="text-muted"> → {request.type === "return" ? request.return_detail?.authorized_hub_name ?? request.destination.label : request.destination.area}</span>
                  </p>
                  <p className="mt-0.5 text-[11px] text-muted">{formatDateTime(request.updated_at)} · {request.next_step}</p>
                </div>
                <Link href={`/customer/requests/${request.id}`} className="btn btn-secondary btn-sm shrink-0">
                  View details
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
