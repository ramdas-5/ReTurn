import { ArrowRight, Info, Layers } from "lucide-react";
import Link from "next/link";

import { PartnerBatchActions } from "@/components/actions/BatchActions";
import { StatusBadge } from "@/components/Status";
import { Callout, Card, EmptyState, PageHeader } from "@/components/ui";
import { formatDateTime, formatKm, formatWeight } from "@/lib/format";
import { requireUser, serverFetchList } from "@/lib/server";
import type { Batch } from "@/lib/types";

export const metadata = { title: "Available batches" };

export default async function PartnerBatchesPage() {
  await requireUser("partner");
  const { data: batches } = await serverFetchList<Batch>("/batches?scope=opportunities");
  const offers = batches.filter((batch) => batch.status === "offered");
  const proposals = batches.filter((batch) => batch.status === "proposed");

  return (
    <div>
      <PageHeader
        eyebrow="Opportunities"
        title="Available batches"
        description="Offers are addressed to you. Proposed batches are visible only if your verified vehicle and service area fit; dispatch still has to offer them before you can accept."
      />

      <div className="mb-6">
        <Callout tone="warning" title="Why can I see a proposed batch but not accept it?">
          Visibility is an eligibility preview, not an assignment. A batch is offered deliberately so acceptance creates a
          clear, auditable commitment.
        </Callout>
      </div>

      <section>
        <h2 className="section-title">Offers awaiting your decision</h2>
        {offers.length === 0 ? (
          <div className="mt-3">
            <EmptyState
              icon={<Layers size={20} aria-hidden />}
              title="No offers waiting"
              description="When an administrator offers you a feasible batch, it appears here with the full route, capacity profile and customer contact rules."
              action={<Link href="/partner" className="btn btn-secondary btn-sm">Back to overview</Link>}
            />
          </div>
        ) : (
          <div className="mt-3 space-y-4">
            {offers.map((batch) => (
              <Card key={batch.id} className="card-pad">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="mono text-[12px] font-medium">{batch.code}</span>
                      <StatusBadge status={batch.status} />
                      <span className="chip chip-amber">Estimated benefit</span>
                    </div>
                    <h3 className="mt-2 text-lg font-bold">
                      {batch.requests.length} parcels · {batch.stops.length} stops
                    </h3>
                    <p className="mt-1 text-[12px] text-muted">
                      {batch.stops[0]?.location.area ?? "—"} → {batch.stops[batch.stops.length - 1]?.location.area ?? "—"} ·{" "}
                      {formatDateTime(batch.offered_at ?? batch.created_at)}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-[11px] uppercase tracking-wide text-muted">Estimated saving</p>
                    <p className="mono text-xl font-semibold text-accent-strong">{batch.savings_percent.toFixed(1)}%</p>
                    <p className="text-[11px] text-muted">{formatKm(batch.savings_km)} vs separate trips</p>
                  </div>
                </div>
                <dl className="mt-4 grid gap-3 border-t pt-4 text-[12px] sm:grid-cols-4">
                  <div>
                    <dt className="text-muted">Shared route</dt>
                    <dd className="mono mt-0.5">{formatKm(batch.distance_km)}</dd>
                  </div>
                  <div>
                    <dt className="text-muted">Duration estimate</dt>
                    <dd className="mt-0.5">{batch.duration_minutes} min</dd>
                  </div>
                  <div>
                    <dt className="text-muted">Peak load</dt>
                    <dd className="mt-0.5">{formatWeight(Math.max(...batch.stops.map((stop) => stop.load_weight_kg), 0))}</dd>
                  </div>
                  <div>
                    <dt className="text-muted">Distance source</dt>
                    <dd className="mt-0.5">{batch.distance_source === "osrm" ? "OSRM road routing" : "Estimated fallback"}</dd>
                  </div>
                </dl>
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <PartnerBatchActions batch={batch} />
                  <Link href={`/partner/batches/${batch.id}`} className="btn btn-secondary btn-sm">
                    Inspect route <ArrowRight size={14} aria-hidden />
                  </Link>
                </div>
              </Card>
            ))}
          </div>
        )}
      </section>

      <section className="mt-8">
        <h2 className="section-title">Proposed batches that fit your profile</h2>
        <p className="mt-1 text-sm text-muted">Awaiting a deliberate dispatch offer. Not yet assigned to you.</p>
        {proposals.length === 0 ? (
          <div className="mt-3 rounded-card border border-dashed bg-surface px-5 py-8 text-center text-sm text-muted">
            No unassigned proposals currently fit your vehicle and service area.
          </div>
        ) : (
          <ul className="mt-3 space-y-3">
            {proposals.map((batch) => (
              <li key={batch.id} className="card p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="mono text-[12px] font-medium">{batch.code}</span>
                      <StatusBadge status={batch.status} />
                      {batch.eligibility?.eligible ? (
                        <span className="chip chip-teal">Fits your vehicle</span>
                      ) : (
                        <span className="chip chip-amber">Not eligible</span>
                      )}
                    </div>
                    <p className="mt-1 text-[12px] text-muted">
                      {batch.requests.length} parcels · {formatKm(batch.distance_km)} shared · estimated {batch.savings_percent.toFixed(1)}% saving
                    </p>
                    {!batch.eligibility?.eligible && batch.eligibility?.reason ? (
                      <p className="mt-1 flex items-center gap-1 text-[11px] text-[#8a5a12]">
                        <Info size={12} aria-hidden /> {batch.eligibility.reason}
                      </p>
                    ) : null}
                  </div>
                  <Link href={`/partner/batches/${batch.id}`} className="btn btn-secondary btn-sm">
                    View details
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
