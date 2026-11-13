import { Activity, AlertTriangle, MapPin, Navigation } from "lucide-react";
import Link from "next/link";

import { BatchMap, BatchStopsLegend, BatchStopsList } from "@/components/BatchStops";
import { StatusBadge } from "@/components/Status";
import { Callout, Card, EmptyState, PageHeader, StatCard } from "@/components/ui";
import { formatDateTime, formatKm, formatWeight } from "@/lib/format";
import { requireUser, serverFetchList } from "@/lib/server";
import type { Batch } from "@/lib/types";

export const metadata = { title: "Route monitor" };

export default async function AdminRoutesPage() {
  await requireUser("admin");
  const { data: batches } = await serverFetchList<Batch>(
    "/batches?status=offered,accepted,in_progress",
  );
  const onRoute = batches.filter((batch) => batch.status === "in_progress");
  const completedStops = batches.reduce(
    (total, batch) => total + batch.stops.filter((stop) => stop.status === "done").length,
    0,
  );
  const totalStops = batches.reduce((total, batch) => total + batch.stops.length, 0);

  return (
    <div>
      <PageHeader
        eyebrow="Execution monitor"
        title="Route monitor"
        description="Planned order and parcel-level stop status for accepted work. No live GPS feed exists; every position and ETA here is a plan estimate."
        actions={<Link href="/admin/batches" className="btn btn-secondary">Batch management</Link>}
      />

      <div className="mb-5 grid gap-4 sm:grid-cols-3">
        <StatCard label="Routes on the road" value={onRoute.length} hint="Batch started by the partner" icon={<Navigation size={17} aria-hidden />} tone="amber" />
        <StatCard label="Accepted, not started" value={batches.filter((batch) => batch.status === "accepted").length} hint="Partner committed" icon={<Activity size={17} aria-hidden />} />
        <StatCard label="Stops completed" value={`${completedStops}/${totalStops}`} hint="Across monitored batches" tone="accent" />
      </div>

      <div className="mb-5">
        <Callout tone="info" title="Monitoring, not surveillance">
          ReTurn shows the accepted plan, stop order and parcel statuses. It does not claim a real-time vehicle location and
          does not invent one when data is missing.
        </Callout>
      </div>

      {batches.length === 0 ? (
        <EmptyState
          icon={<MapPin size={20} aria-hidden />}
          title="No routes to monitor"
          description="Once a partner accepts a batch it appears here. Offers appear immediately, and in-progress routes show stop completion."
          action={<Link href="/admin/batches" className="btn btn-primary btn-sm">Open batch management</Link>}
        />
      ) : (
        <div className="space-y-5">
          {batches.map((batch) => {
            const nextStop = batch.stops.find((stop) => ["pending", "arrived"].includes(stop.status));
            const done = batch.stops.filter((stop) => stop.status === "done").length;
            return (
              <Card key={batch.id} className="overflow-hidden">
                <div className="flex flex-wrap items-start justify-between gap-3 border-b p-4 sm:p-5">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="mono text-[12px] font-semibold">{batch.code}</span>
                      <StatusBadge status={batch.status} />
                      {nextStop ? <span className="chip chip-amber">Next: stop {nextStop.sequence}</span> : null}
                    </div>
                    <p className="mt-1 text-[12px] text-muted">
                      {batch.partner?.name ?? "Unassigned"} · {batch.requests.length} parcels ·{" "}
                      {formatKm(batch.distance_km)} planned · peak {formatWeight(Math.max(...batch.stops.map((stop) => stop.load_weight_kg), 0))}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-right text-[11px]">
                      <p className="text-muted">Stops completed</p>
                      <p className="mono text-base font-semibold">{done}/{batch.stops.length}</p>
                    </div>
                    <Link href={`/admin/batches?batch=${batch.id}`} className="btn btn-secondary btn-sm">
                      Manage
                    </Link>
                  </div>
                </div>
                <div className="grid gap-5 p-4 sm:p-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
                  <div>
                    <BatchMap batch={batch} height="280px" activeSequence={nextStop?.sequence} />
                    <div className="mt-2"><BatchStopsLegend /></div>
                  </div>
                  <div>
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <h2 className="text-sm font-semibold">Stop status</h2>
                      <span className="text-[11px] text-muted">Created {formatDateTime(batch.created_at)}</span>
                    </div>
                    <BatchStopsList stops={batch.stops} compact showLoad={false} />
                  </div>
                </div>
                {batch.requests.some((request) => request.parcel.status === "failed") ? (
                  <div className="border-t bg-red-soft/40 px-4 py-3 text-[12px] text-[#8c2f2f] sm:px-5">
                    <span className="inline-flex items-center gap-1.5">
                      <AlertTriangle size={14} aria-hidden /> A parcel on this route failed. Review the issue queue.
                    </span>
                  </div>
                ) : null}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
