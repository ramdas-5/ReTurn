import { MapPin, Navigation, Play } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { PartnerBatchActions } from "@/components/actions/BatchActions";
import { BatchMap, BatchStopsLegend, BatchStopsList } from "@/components/BatchStops";
import { StatusBadge } from "@/components/Status";
import { Callout, Card, PageHeader } from "@/components/ui";
import { formatDateTime, formatKm, formatWeight } from "@/lib/format";
import { requireUser, serverFetch } from "@/lib/server";
import type { Batch } from "@/lib/types";

export const metadata = { title: "Route execution" };

export default async function PartnerRoutePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireUser("partner");
  const { id } = await params;
  let batch: Batch;
  try {
    batch = await serverFetch<Batch>(`/batches/${id}`);
  } catch {
    notFound();
  }
  const nextStop = batch.stops.find((stop) => ["pending", "arrived"].includes(stop.status));
  const loaded = batch.stops.filter((stop) => stop.kind === "pickup" && stop.status === "done").length;
  const delivered = batch.stops.filter((stop) => stop.kind === "dropoff" && stop.status === "done").length;

  return (
    <div>
      <PageHeader
        back={{ href: `/partner/batches/${batch.id}`, label: "Batch details" }}
        eyebrow="Execution"
        title={`Route · ${batch.code}`}
        description="Follow the numbered sequence. The map is illustrative unless OSRM geometry is available; ETAs are forecasts, not live positions."
        actions={
          <>
            <StatusBadge status={batch.status} />
            <Link href={`/partner/batches/${batch.id}/parcels`} className="btn btn-primary">
              Update parcels
            </Link>
          </>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <div className="space-y-5">
          <Card className="overflow-hidden">
            <div className="p-3">
              <BatchMap batch={batch} height="440px" activeSequence={nextStop?.sequence} />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 border-t px-4 py-3">
              <BatchStopsLegend />
              <span className="text-[11px] text-muted">{formatKm(batch.distance_km)} estimated shared route · {formatKm(batch.baseline_km)} separate-trip baseline</span>
            </div>
          </Card>

          <Card className="card-pad">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="section-title">Ordered itinerary</h2>
              <span className="chip chip-neutral">{batch.stops.length} stops</span>
            </div>
            <div className="mt-4">
              <BatchStopsList stops={batch.stops} />
            </div>
          </Card>
        </div>

        <div className="space-y-5">
          <Card className="overflow-hidden">
            <div className="bg-ink p-5 text-white">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-lime">Next stop</p>
              {nextStop ? (
                <>
                  <h2 className="mt-2 text-[22px] font-bold">
                    {nextStop.kind === "pickup" ? "Pickup" : "Drop-off"} · {nextStop.location.area}
                  </h2>
                  <p className="mt-1 text-sm text-white/70">{nextStop.location.label}</p>
                  <p className="mt-2 text-[12px] text-white/50">
                    ETA {formatDateTime(nextStop.planned_arrival)} · {nextStop.request?.parcel_code ?? ""}
                  </p>
                </>
              ) : (
                <h2 className="mt-2 text-[22px] font-bold">All stops resolved</h2>
              )}
              <div className="mt-4 grid grid-cols-3 gap-2 text-[12px]">
                <div>
                  <p className="text-white/45">Loaded</p>
                  <p className="mt-0.5">{loaded} pickups</p>
                </div>
                <div>
                  <p className="text-white/45">Delivered</p>
                  <p className="mt-0.5">{delivered} drop-offs</p>
                </div>
                <div>
                  <p className="text-white/45">Peak load</p>
                  <p className="mt-0.5">{formatWeight(Math.max(...batch.stops.map((stop) => stop.load_weight_kg), 0))}</p>
                </div>
              </div>
              <div className="mt-4">
                <PartnerBatchActions batch={batch} />
              </div>
            </div>
            <div className="space-y-2 p-4 text-[12px] leading-5 text-muted">
              <p className="flex items-start gap-1.5"><Navigation size={14} className="mt-0.5 shrink-0 text-accent" aria-hidden /> Route order is fixed by the accepted plan. Do not deliver a parcel before its pickup.</p>
              <p className="flex items-start gap-1.5"><MapPin size={14} className="mt-0.5 shrink-0 text-accent" aria-hidden /> Customer addresses are disclosed only for accepted work.</p>
              <p className="flex items-start gap-1.5"><Play size={14} className="mt-0.5 shrink-0 text-accent" aria-hidden /> Parcel statuses are updated individually on the parcels view.</p>
            </div>
          </Card>

          {batch.status === "accepted" ? (
            <Callout tone="info" title="Start the route to unlock parcel updates">
              Status updates require the batch to be in progress. Starting records the execution time and notifies customers.
            </Callout>
          ) : null}
          {batch.status === "in_progress" ? (
            <Callout tone="warning" title="Route in progress">
              All parcel events are timestamped and attributed to you. Failed handovers require a reason and create an issue.
            </Callout>
          ) : null}

          <Card className="card-pad">
            <h2 className="section-title">Parcels on this route</h2>
            <ul className="mt-3 space-y-2">
              {batch.requests.map((request) => (
                <li key={request.id} className="rounded-control border bg-surface-muted p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="mono text-[11px]">{request.code}</span>
                    <StatusBadge status={request.parcel.status} />
                  </div>
                  <p className="mt-1 text-[12px]">{request.parcel.description}</p>
                  <Link href={`/partner/batches/${batch.id}/parcels`} className="mt-2 inline-flex text-[11px] font-medium text-accent hover:underline">
                    Manage this parcel
                  </Link>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}
