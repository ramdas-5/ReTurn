import { ArrowRight, MapPin, Package, Phone, UserRound } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { PartnerBatchActions } from "@/components/actions/BatchActions";
import { BatchMap, BatchStopsList } from "@/components/BatchStops";
import { ServiceBadge, StatusBadge } from "@/components/Status";
import { Callout, Card, PageHeader, StatCard } from "@/components/ui";
import { formatDateTime, formatKm, formatWeight } from "@/lib/format";
import { requireUser, serverFetch } from "@/lib/server";
import type { Batch } from "@/lib/types";

export const metadata = { title: "Batch details" };

export default async function PartnerBatchDetailPage({
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

  const contactsVisible = ["accepted", "in_progress", "completed"].includes(batch.status);
  const nextStop = batch.stops.find((stop) => ["pending", "arrived"].includes(stop.status));

  return (
    <div>
      <PageHeader
        back={{ href: "/partner/batches", label: "Available batches" }}
        eyebrow="Batch detail"
        title={batch.code}
        description={`${batch.requests.length} parcels · ${batch.stops.length} ordered stops · ${formatKm(batch.distance_km)} estimated shared route.`}
        actions={
          <>
            <StatusBadge status={batch.status} />
            <span className="chip chip-amber">Estimated figures</span>
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Estimated saving" value={`${batch.savings_percent.toFixed(1)}%`} hint={`${formatKm(batch.savings_km)} vs separate trips`} tone="accent" />
        <StatCard label="Duration estimate" value={`${batch.duration_minutes} min`} hint="Includes service time" />
        <StatCard label="Peak load" value={formatWeight(Math.max(...batch.stops.map((stop) => stop.load_weight_kg), 0))} hint="Checked at every stop" />
        <StatCard label="Distance source" value={batch.distance_source === "osrm" ? "OSRM" : "Estimated"} hint={batch.distance_source === "osrm" ? "Road routing" : "Haversine × road factor"} tone="blue" />
      </div>

      {batch.eligibility && !batch.eligibility.eligible ? (
        <div className="mt-5">
          <Callout tone="warning" title="This batch does not fit your current profile">
            {batch.eligibility.reason}. Update your vehicle or availability if that is still accurate.
          </Callout>
        </div>
      ) : null}

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <div className="space-y-6">
          <Card className="card-pad">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="section-title">Route map</h2>
              <Link href={`/partner/batches/${batch.id}/route`} className="btn btn-secondary btn-sm">
                Execution view <ArrowRight size={14} aria-hidden />
              </Link>
            </div>
            <div className="mt-4">
              <BatchMap batch={batch} height="330px" activeSequence={nextStop?.sequence} />
            </div>
          </Card>

          <Card className="card-pad">
            <h2 className="section-title">Ordered stops</h2>
            <p className="mt-1 text-sm text-muted">Pickups and drop-offs are fixed by the accepted feasible plan.</p>
            <div className="mt-4">
              <BatchStopsList stops={batch.stops} />
            </div>
          </Card>

          <Card className="card-pad">
            <h2 className="section-title">Parcels & customer handover</h2>
            <div className="mt-3 space-y-3">
              {batch.requests.map((request) => (
                <div key={request.id} className="rounded-control border p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="mono text-[12px] font-medium">{request.code}</span>
                      <ServiceBadge type={request.type} />
                    </div>
                    <StatusBadge status={request.parcel.status} />
                  </div>
                  <p className="mt-2 flex items-center gap-1.5 text-sm">
                    <Package size={14} className="text-muted" aria-hidden /> {request.parcel.description} ·{" "}
                    {formatWeight(request.parcel.weight_kg)} · {request.parcel.volume_m3.toFixed(3)} m³
                  </p>
                  <div className="mt-2 grid gap-2 text-[12px] text-muted sm:grid-cols-2">
                    <p className="flex items-start gap-1.5">
                      <MapPin size={13} className="mt-0.5 shrink-0" aria-hidden /> Pickup:{" "}
                      {contactsVisible ? `${request.pickup.address_line}, ${request.pickup.area}` : request.pickup.area}
                    </p>
                    <p className="flex items-start gap-1.5">
                      <MapPin size={13} className="mt-0.5 shrink-0" aria-hidden /> Drop-off:{" "}
                      {request.type === "return"
                        ? request.return_detail?.authorized_hub_name ?? request.destination.label
                        : `${request.destination.address_line}, ${request.destination.area}`}
                    </p>
                  </div>
                  {contactsVisible ? (
                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-muted">
                      <span className="flex items-center gap-1.5">
                        <UserRound size={13} aria-hidden /> {request.customer?.name ?? "Customer"}
                      </span>
                      {request.customer?.phone ? (
                        <span className="flex items-center gap-1.5">
                          <Phone size={13} aria-hidden /> {request.customer.phone}
                        </span>
                      ) : null}
                      {request.type === "parcel" && request.recipient?.name ? (
                        <span>Recipient: {request.recipient.name}{request.recipient.phone ? ` · ${request.recipient.phone}` : ""}</span>
                      ) : null}
                    </div>
                  ) : (
                    <p className="mt-2 text-[11px] text-muted">
                      Customer contact details unlock after you accept the batch.
                    </p>
                  )}
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Link href={`/partner/batches/${batch.id}/parcels`} className="btn btn-secondary btn-sm">
                      Update parcel
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        <div className="space-y-6">
          <Card className="card-pad">
            <h2 className="section-title">Your decision</h2>
            <p className="mt-1 text-sm leading-6 text-muted">
              Accepting commits your vehicle for this feasible plan. Decline only if you cannot run it; the batch stays
              reserved for another offer.
            </p>
            <div className="mt-4">
              <PartnerBatchActions batch={batch} />
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <Link href={`/partner/batches/${batch.id}/route`} className="btn btn-secondary btn-sm">Route</Link>
              <Link href={`/partner/batches/${batch.id}/parcels`} className="btn btn-secondary btn-sm">Parcels</Link>
            </div>
          </Card>

          <Card className="card-pad">
            <h2 className="section-title">Compatibility reasons</h2>
            <ul className="mt-2 space-y-1.5 text-[12px] leading-5 text-muted">
              {(batch.explanation.included_reasons ?? []).map((reason) => (
                <li key={reason}>• {reason}</li>
              ))}
            </ul>
            <p className="mt-3 text-[11px] leading-4 text-muted">
              Route method: {batch.route_method}. Distance source:{" "}
              {batch.explanation.distance_source_label ?? batch.distance_source}.
            </p>
          </Card>

          <Card className="card-pad">
            <h2 className="section-title">Assignment history</h2>
            <ol className="mt-3 space-y-3">
              {batch.assignment_history.length === 0 ? (
                <li className="text-[12px] text-muted">No assignment events yet.</li>
              ) : (
                batch.assignment_history.map((event) => (
                  <li key={event.id} className="border-l-2 border-line pl-3">
                    <p className="text-[12px] font-medium capitalize">{event.action.replaceAll("_", " ")}</p>
                    <p className="text-[11px] text-muted">
                      {formatDateTime(event.created_at)} · {event.actor_name}
                      {event.partner_name ? ` · ${event.partner_name}` : ""}
                    </p>
                    {event.reason ? <p className="mt-0.5 text-[11px] text-muted">{event.reason}</p> : null}
                  </li>
                ))
              )}
            </ol>
          </Card>

          <Callout tone="warning" title="Estimates, not telemetry">
            Arrival times are modelled forecasts from the accepted plan. No live GPS position is shown or implied.
          </Callout>
        </div>
      </div>
    </div>
  );
}
