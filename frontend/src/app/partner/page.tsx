import {
  ArrowRight,
  CheckCircle2,
  Clock3,
  MapPin,
  Navigation,
  Package,
  ShieldCheck,
  Truck,
} from "lucide-react";
import Link from "next/link";

import { PartnerBatchActions } from "@/components/actions/BatchActions";
import { BatchMap, BatchStopsList } from "@/components/BatchStops";
import { StatusBadge, VerificationBadge } from "@/components/Status";
import { Callout, Card, EmptyState, PageHeader, StatCard } from "@/components/ui";
import { formatDateTime, formatKm, formatWeight } from "@/lib/format";
import { requireUser, serverFetch, serverFetchList } from "@/lib/server";
import type { Batch, DeliveryRequest, Issue, PartnerProfile } from "@/lib/types";

export const metadata = { title: "Overview" };

type PartnerMe = {
  profile: PartnerProfile;
  stats: {
    assigned_batches: number;
    active_batches: number;
    completed_batches: number;
    completed_parcels: number;
  };
};

export default async function PartnerDashboard() {
  const me = await requireUser("partner");
  const [{ profile, stats }, { data: batches }, { data: issues }] = await Promise.all([
    serverFetch<PartnerMe>("/partners/me"),
    serverFetchList<Batch>("/batches"),
    serverFetchList<Issue>("/issues?status=open"),
  ]);

  const active = batches.find((batch) => ["accepted", "in_progress"].includes(batch.status));
  const offered = batches.find((batch) => batch.status === "offered");
  const nextStop = active?.stops.find((stop) => ["pending", "arrived"].includes(stop.status)) ?? active?.stops[0];
  const parcelsLoaded = active?.stops.filter((stop) => stop.kind === "pickup" && stop.status === "done").length ?? 0;

  return (
    <div>
      <PageHeader
        eyebrow="Partner route desk"
        title={`Good route, ${me.user.name.split(" ")[0]}`}
        description="Your vehicle, capacity and availability decide which batches you can accept. Execution stays parcel-by-parcel."
        actions={
          <>
            <VerificationBadge status={profile.verification_status} />
            <Link href="/partner/batches" className="btn btn-primary">
              Available batches <ArrowRight size={15} aria-hidden />
            </Link>
          </>
        }
      />

      {profile.verification_status !== "verified" ? (
        <div className="mb-5">
          <Callout tone="warning" title="Verification is still pending">
            You can update your vehicle profile now. Batch offers unlock after an administrator verifies your account
            {profile.verification_note ? ` — note: ${profile.verification_note}` : "."}
          </Callout>
        </div>
      ) : null}
      {profile.availability !== "available" ? (
        <div className="mb-5">
          <Callout tone="info" title="You are not marked available">
            Set availability to “Available” in your vehicle profile to receive new offers. Existing accepted work is not
            cancelled automatically.
          </Callout>
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Active batches" value={stats.active_batches} hint="Accepted or on route" icon={<Navigation size={17} aria-hidden />} tone="accent" />
        <StatCard label="Completed batches" value={stats.completed_batches} hint="All-time finished work" icon={<CheckCircle2 size={17} aria-hidden />} />
        <StatCard label="Parcels delivered" value={stats.completed_parcels} hint="Across completed batches" icon={<Package size={17} aria-hidden />} tone="blue" />
        <StatCard label="Open issues" value={issues.length} hint="Reported on your work or by you" icon={<Clock3 size={17} aria-hidden />} tone={issues.length ? "amber" : "default"} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Card className="overflow-hidden" as="section">
          <div className="bg-ink p-5 text-white sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-lime">Next stop</p>
              {active ? <StatusBadge status={active.status} /> : null}
            </div>
            {active ? (
              <>
                <h2 className="mt-2 text-[24px] font-bold leading-tight">
                  {nextStop?.kind === "pickup" ? "Pickup" : "Drop-off"} · {nextStop?.location.area}
                </h2>
                <p className="mt-1 text-sm text-white/70">{nextStop?.location.label}</p>
                <div className="mt-4 grid grid-cols-2 gap-3 text-[12px] sm:grid-cols-4">
                  <div>
                    <p className="text-white/45">Batch</p>
                    <p className="mono mt-0.5">{active.code}</p>
                  </div>
                  <div>
                    <p className="text-white/45">Planned ETA</p>
                    <p className="mt-0.5">{nextStop ? formatDateTime(nextStop.planned_arrival) : "—"}</p>
                  </div>
                  <div>
                    <p className="text-white/45">Parcels loaded</p>
                    <p className="mt-0.5">{parcelsLoaded} / {active.requests.length}</p>
                  </div>
                  <div>
                    <p className="text-white/45">Est. route</p>
                    <p className="mt-0.5">{formatKm(active.distance_km)}</p>
                  </div>
                </div>
                <div className="mt-5 flex flex-wrap gap-2">
                  <Link href={`/partner/batches/${active.id}/route`} className="btn btn-lime">
                    Open route
                  </Link>
                  <Link href={`/partner/batches/${active.id}/parcels`} className="btn border border-white/20 bg-white/5 text-white hover:bg-white/10">
                    Update parcels
                  </Link>
                </div>
                <div className="mt-4">
                  <PartnerBatchActions batch={active} />
                </div>
              </>
            ) : offered ? (
              <>
                <h2 className="mt-2 text-[22px] font-bold">A batch is waiting for your decision</h2>
                <p className="mt-1 text-sm text-white/70">
                  {offered.code} · {offered.requests.length} parcels · estimated saving {formatKm(offered.savings_km)}.
                </p>
                <div className="mt-4">
                  <PartnerBatchActions batch={offered} />
                </div>
                <Link href={`/partner/batches/${offered.id}`} className="mt-4 inline-flex text-sm text-lime hover:underline">
                  Inspect batch details
                </Link>
              </>
            ) : (
              <>
                <h2 className="mt-2 text-[22px] font-bold">No active route</h2>
                <p className="mt-1 text-sm text-white/65">
                  When dispatch offers a feasible batch, this panel becomes your next stop. Nearby loads alone are never
                  enough to assign one.
                </p>
                <Link href="/partner/batches" className="btn btn-lime mt-4">
                  Browse available batches
                </Link>
              </>
            )}
          </div>
          {active ? (
            <div className="space-y-4 p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="section-title">Route overview</h2>
                <span className="chip chip-neutral">{active.stops.length} stops</span>
              </div>
              <BatchMap batch={active} height="260px" activeSequence={nextStop?.sequence} />
              <BatchStopsList stops={active.stops} compact />
            </div>
          ) : (
            <div className="p-5">
              <EmptyState
                icon={<Truck size={20} aria-hidden />}
                title="Your route will appear here"
                description="Accept a batch to see the ordered pickups and drop-offs, the capacity profile and the individual parcels."
              />
            </div>
          )}
        </Card>

        <div className="space-y-6">
          <Card className="card-pad">
            <div className="flex items-center justify-between gap-2">
              <h2 className="section-title">Vehicle readiness</h2>
              <ShieldCheck size={18} className="text-accent" aria-hidden />
            </div>
            <dl className="mt-3 space-y-3 text-[13px]">
              <div className="flex justify-between gap-2">
                <dt className="text-muted">Vehicle</dt>
                <dd className="font-medium capitalize">{profile.vehicle_type}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted">Weight limit</dt>
                <dd className="mono">{formatWeight(profile.max_weight_kg)}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted">Volume limit</dt>
                <dd className="mono">{profile.max_volume_m3.toFixed(3)} m³</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted">Handling</dt>
                <dd>{[profile.accepts_fragile ? "Fragile" : null, profile.accepts_restricted ? "Restricted" : null].filter(Boolean).join(", ") || "Standard only"}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted">Service areas</dt>
                <dd className="max-w-[60%] text-right">{profile.service_areas.length ? profile.service_areas.join(", ") : "No restriction"}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted">Availability</dt>
                <dd className="capitalize">{profile.availability.replaceAll("_", " ")}</dd>
              </div>
            </dl>
            <Link href="/partner/profile" className="btn btn-secondary btn-sm mt-4 w-full">
              Update vehicle & availability
            </Link>
          </Card>

          <Card className="card-pad">
            <h2 className="section-title">Recent exceptions</h2>
            {issues.length === 0 ? (
              <p className="mt-2 text-sm leading-6 text-muted">No open issues on your work. Report a problem from any batch or parcel.</p>
            ) : (
              <ul className="mt-3 space-y-3">
                {issues.slice(0, 3).map((issue) => (
                  <li key={issue.id} className="rounded-control border bg-surface-muted p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="mono text-[11px]">{issue.request?.code ?? `Issue #${issue.id}`}</span>
                      <span className="chip chip-amber capitalize">{issue.severity}</span>
                    </div>
                    <p className="mt-1 text-[12px] leading-5 text-muted">{issue.description}</p>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card className="card-pad">
            <h2 className="section-title">Next actions</h2>
            <ul className="mt-2 space-y-2 text-[13px] leading-5 text-muted">
              <li className="flex gap-2"><MapPin size={14} className="mt-0.5 shrink-0 text-accent" aria-hidden /> Follow the numbered stop order; pickup always precedes that parcel&apos;s delivery.</li>
              <li className="flex gap-2"><Package size={14} className="mt-0.5 shrink-0 text-accent" aria-hidden /> Update each parcel separately — never infer one parcel&apos;s state from another.</li>
              <li className="flex gap-2"><Clock3 size={14} className="mt-0.5 shrink-0 text-accent" aria-hidden /> Report failed handovers with a reason so an audited issue is created.</li>
            </ul>
          </Card>
        </div>
      </div>
      {offered && active ? (
        <div className="mt-6">
          <Callout tone="info" title="You also have a pending offer">
            {offered.code} is still awaiting your decision.{" "}
            <Link href={`/partner/batches/${offered.id}`} className="link">Review it</Link>.
          </Callout>
        </div>
      ) : null}
    </div>
  );
}
