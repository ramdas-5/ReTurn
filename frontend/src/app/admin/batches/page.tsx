import { ArrowRight, Layers } from "lucide-react";
import Link from "next/link";

import { AdminBatchActions } from "@/components/actions/BatchActions";
import { BatchMap, BatchStopsList } from "@/components/BatchStops";
import { StatusBadge } from "@/components/Status";
import MatchingConsole from "@/components/admin/MatchingConsole";
import { Callout, Card, EmptyState, PageHeader, StatCard } from "@/components/ui";
import { formatDateTime, formatKm, formatWeight } from "@/lib/format";
import { requireUser, serverFetchList } from "@/lib/server";
import type { Batch, PartnerProfile } from "@/lib/types";

export const metadata = { title: "Batch management" };

export default async function AdminBatchesPage({
  searchParams,
}: {
  searchParams: Promise<{ batch?: string }>;
}) {
  await requireUser("admin");
  const params = await searchParams;
  const [{ data: batches }, { data: partners }] = await Promise.all([
    serverFetchList<Batch>("/batches"),
    serverFetchList<PartnerProfile>("/partners"),
  ]);

  const selectedId = params.batch
    ? Number(params.batch)
    : (batches.find((batch) => ["proposed", "offered", "accepted", "in_progress"].includes(batch.status)) ??
        batches[0])?.id;
  const selected = batches.find((batch) => batch.id === selectedId) ?? null;
  const proposed = batches.filter((batch) => batch.status === "proposed");
  const offered = batches.filter((batch) => batch.status === "offered");
  const active = batches.filter((batch) => ["accepted", "in_progress"].includes(batch.status));

  return (
    <div>
      <PageHeader
        eyebrow="Dispatch"
        title="Batch management"
        description="Preview feasible groups, create proposals, offer verified partners, reassign with a reason and monitor execution. Commit always rechecks feasibility and reservations."
        actions={
          <Link href="/admin/routes" className="btn btn-secondary">
            Route monitor <ArrowRight size={15} aria-hidden />
          </Link>
        }
      />

      <div className="mb-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Proposed" value={proposed.length} hint="Unassigned reservations" icon={<Layers size={17} aria-hidden />} tone="blue" />
        <StatCard label="Offered" value={offered.length} hint="Awaiting partner decision" tone="amber" />
        <StatCard label="Accepted" value={active.length} hint="Ready or on route" tone="accent" />
        <StatCard label="Total batches" value={batches.length} hint="Including history" />
      </div>

      <MatchingConsole />

      <div className="mt-6 grid gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.25fr)]">
        <Card className="overflow-hidden">
          <div className="border-b px-4 py-3">
            <h2 className="text-sm font-semibold">Batches</h2>
            <p className="text-[11px] text-muted">Newest first. Select a batch to manage it.</p>
          </div>
          {batches.length === 0 ? (
            <div className="p-4">
              <EmptyState title="No batches yet" description="Run a matching preview and create the first feasible proposal." />
            </div>
          ) : (
            <ul className="max-h-[620px] divide-y overflow-y-auto">
              {batches.map((batch) => (
                <li key={batch.id}>
                  <Link
                    href={`/admin/batches?batch=${batch.id}#batch-detail`}
                    className={`block px-4 py-3 transition hover:bg-surface-muted ${
                      selectedId === batch.id ? "bg-accent-soft/50" : ""
                    }`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="mono text-[12px] font-medium">{batch.code}</span>
                      <StatusBadge status={batch.status} />
                    </div>
                    <p className="mt-1 text-[12px] text-muted">
                      {batch.request_count ?? batch.requests.length} requests · {batch.stops.length} stops ·{" "}
                      {batch.partner?.name ?? "unassigned"}
                    </p>
                    <p className="text-[11px] text-muted">
                      Estimated {formatKm(batch.savings_km)} saved ({batch.savings_percent.toFixed(1)}%) ·{" "}
                      {formatDateTime(batch.created_at)}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <div id="batch-detail" className="space-y-5">
          {selected ? (
            <>
              <Card className="card-pad">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="mono text-[12px] font-semibold">{selected.code}</span>
                      <StatusBadge status={selected.status} />
                      <span className="chip chip-amber">Estimated benefit</span>
                    </div>
                    <h2 className="mt-2 text-lg font-bold">
                      {selected.request_count ?? selected.requests.length} parcels · {selected.stops.length} stops
                    </h2>
                    <p className="mt-1 text-[12px] leading-5 text-muted">
                      {selected.partner?.name ? `Assigned to ${selected.partner.name}` : "No partner assigned"} ·{" "}
                      {formatDateTime(selected.created_at)}
                    </p>
                  </div>
                  <div className="text-right text-[12px]">
                    <p className="text-muted">Estimated saving</p>
                    <p className="mono text-lg font-semibold text-accent-strong">{selected.savings_percent.toFixed(1)}%</p>
                    <p className="text-muted">{formatKm(selected.savings_km)}</p>
                  </div>
                </div>

                <dl className="mt-4 grid gap-3 border-t pt-4 text-[12px] sm:grid-cols-4">
                  <div>
                    <dt className="text-muted">Shared route</dt>
                    <dd className="mono mt-0.5">{formatKm(selected.distance_km)}</dd>
                  </div>
                  <div>
                    <dt className="text-muted">Separate baseline</dt>
                    <dd className="mono mt-0.5">{formatKm(selected.baseline_km)}</dd>
                  </div>
                  <div>
                    <dt className="text-muted">Peak load</dt>
                    <dd className="mt-0.5">{formatWeight(Math.max(...selected.stops.map((stop) => stop.load_weight_kg), 0))}</dd>
                  </div>
                  <div>
                    <dt className="text-muted">Source</dt>
                    <dd className="mt-0.5">{selected.distance_source === "osrm" ? "OSRM" : "Estimated"}</dd>
                  </div>
                </dl>

                <div className="mt-4">
                  <AdminBatchActions key={selected.id} batch={selected} partners={partners} />
                </div>
              </Card>

              <Card className="card-pad">
                <h2 className="section-title">Route & stops</h2>
                <div className="mt-3">
                  <BatchMap batch={selected} height="280px" />
                </div>
                <div className="mt-4">
                  <BatchStopsList stops={selected.stops} compact />
                </div>
              </Card>

              <Card className="card-pad">
                <h2 className="section-title">Compatibility & method</h2>
                <ul className="mt-2 space-y-1.5 text-[12px] leading-5 text-muted">
                  {(selected.explanation.included_reasons ?? []).map((reason) => (
                    <li key={reason}>• {reason}</li>
                  ))}
                </ul>
                <div className="mt-3 border-t pt-3">
                  <p className="text-[11px] leading-4 text-muted">
                    {selected.route_method}. {selected.explanation.distance_source_label ?? selected.distance_source}.
                  </p>
                  {selected.explanation.note ? (
                    <p className="mt-1 text-[11px] leading-4 text-muted">Dispatch note: {selected.explanation.note}</p>
                  ) : null}
                </div>
              </Card>

              {selected.assignment_history.length ? (
                <Card className="card-pad">
                  <h2 className="section-title">Assignment audit</h2>
                  <ol className="mt-3 space-y-3">
                    {selected.assignment_history.map((event) => (
                      <li key={event.id} className="border-l-2 border-line pl-3">
                        <p className="text-[12px] font-medium capitalize">{event.action.replaceAll("_", " ")}</p>
                        <p className="text-[11px] text-muted">
                          {formatDateTime(event.created_at)} · {event.actor_name}
                          {event.partner_name ? ` → ${event.partner_name}` : ""}
                        </p>
                        {event.reason ? <p className="mt-0.5 text-[11px] text-muted">{event.reason}</p> : null}
                      </li>
                    ))}
                  </ol>
                </Card>
              ) : null}
            </>
          ) : (
            <EmptyState
              icon={<Layers size={19} aria-hidden />}
              title="No batch selected"
              description="Create a proposal with the matching console, then manage offers and execution here."
            />
          )}
        </div>
      </div>

      <div className="mt-6">
        <Callout tone="warning" title="Audited dispatch rules">
          A batch cannot be offered to an unverified, unavailable or ineligible partner. Reassignment requires a reason.
          Cancelling a batch releases every reserved request; in-progress batches cannot be cancelled here.
        </Callout>
      </div>
    </div>
  );
}
