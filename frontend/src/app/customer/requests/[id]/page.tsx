import {
  ArrowLeftRight,
  CalendarClock,
  MapPin,
  Package,
  Truck,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import CancelRequestButton from "@/components/actions/CancelRequestButton";
import IssueForm from "@/components/actions/IssueForm";
import RouteMap, { type MapStop } from "@/components/RouteMap";
import { ServiceBadge, StatusBadge } from "@/components/Status";
import Timeline from "@/components/Timeline";
import { Callout, Card, Mono, PageHeader } from "@/components/ui";
import { formatDateTime, formatVolume, formatWeight, formatWindow, serviceLabel } from "@/lib/format";
import { requireUser, serverFetch } from "@/lib/server";
import type { CustomerBatchContext, DeliveryRequest } from "@/lib/types";

export const metadata = { title: "Request tracking" };

export default async function CustomerRequestDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireUser("customer");
  const { id } = await params;
  let request: DeliveryRequest;
  try {
    request = await serverFetch<DeliveryRequest>(`/requests/${id}`);
  } catch {
    notFound();
  }

  const isBatch = request.batch && "stops" in request.batch;
  const batch = isBatch ? (request.batch as CustomerBatchContext) : null;
  const batchSummary = request.batch && !isBatch ? request.batch : null;
  const canCancel = ["pending_matching", "batched"].includes(request.status);
  const mapStops: MapStop[] = batch
    ? batch.stops.map((stop) => ({
        id: stop.id,
        code: stop.request?.code,
        label: stop.location.label,
        area: stop.location.area,
        latitude: stop.location.latitude,
        longitude: stop.location.longitude,
        kind: stop.kind,
        sequence: stop.sequence,
        status: stop.status,
      }))
    : [];

  return (
    <div>
      <PageHeader
        back={{ href: "/customer/requests", label: "My requests" }}
        eyebrow="Parcel journey"
        title={request.code}
        description={
          <>
            Created {formatDateTime(request.created_at)} · {serviceLabel(request.type)}. {request.next_step}
          </>
        }
        actions={
          <>
            <StatusBadge status={request.status} />
            <ServiceBadge type={request.type} />
            {canCancel ? <CancelRequestButton requestId={request.id} code={request.code} /> : null}
          </>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <div className="space-y-6">
          <Card className="card-pad">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="section-title">Journey</h2>
              <span className="chip chip-neutral">Parcel-level tracking</span>
            </div>
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <div className="rounded-control border bg-surface-muted p-4">
                <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">
                  <MapPin size={13} aria-hidden /> Pickup
                </p>
                <p className="mt-2 text-sm font-medium">{request.pickup.label}</p>
                <p className="text-xs text-muted">{request.pickup.address_line}, {request.pickup.area}</p>
                <p className="mt-2 text-[11px] text-muted">
                  Window: {formatWindow(request.pickup_window_start, request.pickup_window_end)}
                </p>
              </div>
              <div className={`rounded-control border p-4 ${request.type === "return" ? "border-[#c3e9da] bg-accent-soft/60" : "border-[#cfe4f3] bg-blue-soft/60"}`}>
                <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">
                  {request.type === "return" ? <ArrowLeftRight size={13} aria-hidden /> : <Truck size={13} aria-hidden />}
                  {request.type === "return" ? "Authorised return destination" : "Recipient delivery address"}
                </p>
                <p className="mt-2 text-sm font-medium">
                  {request.type === "return"
                    ? request.return_detail?.authorized_hub_name ?? request.destination.label
                    : request.recipient?.name ?? "Recipient"}
                </p>
                <p className="text-xs text-muted">
                  {request.destination.address_line}, {request.destination.area}
                </p>
                {request.type === "return" && request.return_detail?.return_reference ? (
                  <p className="mt-2 text-[11px] text-muted">
                    Return ref: <Mono>{request.return_detail.return_reference}</Mono>
                  </p>
                ) : null}
                {request.type === "parcel" && request.recipient?.phone ? (
                  <p className="mt-2 text-[11px] text-muted">Recipient phone: {request.recipient.phone}</p>
                ) : null}
                {request.type === "parcel" && request.recipient?.instructions ? (
                  <p className="mt-1 text-[11px] text-muted">Instructions: {request.recipient.instructions}</p>
                ) : null}
              </div>
            </div>

            <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-[11px] uppercase tracking-wide text-muted">Delivery deadline</dt>
                <dd className="mt-0.5 flex items-center gap-1.5">
                  <CalendarClock size={14} className="text-muted" aria-hidden /> {formatDateTime(request.delivery_deadline)}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase tracking-wide text-muted">Parcel</dt>
                <dd className="mt-0.5 flex items-center gap-1.5">
                  <Package size={14} className="text-muted" aria-hidden /> {formatWeight(request.parcel.weight_kg)} · {formatVolume(request.parcel.volume_m3)}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase tracking-wide text-muted">Tracking number</dt>
                <dd className="mono mt-0.5 text-[12px]">{request.parcel.tracking_number}</dd>
              </div>
            </dl>

            {request.parcel.handling.length ? (
              <p className="mt-4 text-[12px] text-muted">Handling: {request.parcel.handling.join(", ")}</p>
            ) : null}
            {request.notes ? (
              <p className="mt-3 rounded-control bg-surface-muted px-3 py-2 text-[12px] leading-5 text-muted">
                Your note: {request.notes}
              </p>
            ) : null}
            {request.failure_reason ? (
              <div className="mt-4">
                <Callout tone="danger" title="Delivery issue recorded">{request.failure_reason}</Callout>
              </div>
            ) : null}
          </Card>

          <Card className="card-pad">
            <h2 className="section-title">Parcel timeline</h2>
            <p className="mt-1 text-sm text-muted">
              Each parcel has its own history, even when it travels in a shared batch.
            </p>
            <div className="mt-5">
              <Timeline events={request.tracking ?? []} />
            </div>
          </Card>

          <Card className="card-pad">
            <h2 className="section-title">Report an issue</h2>
            <p className="mt-1 text-sm text-muted">
              Raising an issue does not silently change the parcel&apos;s status. Dispatch reviews it with the history
              intact.
            </p>
            <div className="mt-3">
              <IssueForm requestId={request.id} compact />
            </div>
          </Card>
        </div>

        <div className="space-y-6">
          <Card className="card-pad" id="batch">
            <h2 className="section-title">Shared batch</h2>
            {batch ? (
              <>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <span className="mono text-[12px] font-medium">{batch.code}</span>
                  <StatusBadge status={batch.status} />
                  <span className="chip chip-amber">Estimated</span>
                </div>
                <p className="mt-2 text-[12px] leading-5 text-muted">
                  {batch.parcel_count > 1
                    ? `${batch.parcel_count} parcels share this route. You only see your own stop details.`
                    : "This route currently carries your parcel."}
                </p>
                <div className="mt-4">
                  <RouteMap stops={mapStops} height="240px" geometrySource="estimated" />
                </div>
                <p className="mt-2 text-[11px] leading-4 text-muted">
                  Illustrative connector — estimated, not road navigation. No live GPS is displayed.
                </p>
                <dl className="mt-4 space-y-2 text-[12px]">
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted">Estimated shared distance</dt>
                    <dd className="mono">{batch.distance_km.toFixed(1)} km</dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted">Estimated saving vs separate trips</dt>
                    <dd className="mono">{batch.savings_percent.toFixed(1)}%</dd>
                  </div>
                </dl>
                {batch.partner ? (
                  <div className="mt-4 rounded-control border bg-surface-muted p-3">
                    <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">
                      <UserRound size={13} aria-hidden /> Assigned partner
                    </p>
                    <p className="mt-1 text-sm font-medium">{batch.partner.name}</p>
                    {batch.partner.phone ? <p className="text-xs text-muted">{batch.partner.phone}</p> : null}
                  </div>
                ) : null}
                <div className="mt-4">
                  <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted">Your stops</p>
                  <ul className="space-y-2">
                    {batch.stops.map((stop) => (
                      <li key={stop.id} className="flex items-start gap-2 text-[12px]">
                        <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[9px] font-bold text-white ${stop.kind === "pickup" ? "bg-accent" : "bg-[#2c6ca2]"}`}>
                          {stop.sequence}
                        </span>
                        <span>
                          <span className="font-medium capitalize">{stop.kind}</span> · {stop.location.label}
                          <span className="block text-[11px] text-muted">{formatDateTime(stop.planned_arrival)}</span>
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              </>
            ) : (
              <div className="mt-3 space-y-3">
                <p className="text-sm leading-6 text-muted">
                  No shared batch yet. {batchSummary ? `The last proposal ${batchSummary.code} was not completed.` : "ReTurn is waiting for compatible requests."}
                </p>
                <Callout tone="info" title="Grouping is not guaranteed">
                  A compatible request nearby still has to fit pickup windows, capacity, handling, deadline and a positive
                  estimated saving. If none of that works, your request stays independent.
                </Callout>
              </div>
            )}
          </Card>

          <Card className="card-pad">
            <h2 className="section-title">Reference</h2>
            <dl className="mt-3 space-y-3 text-[12px]">
              <div>
                <dt className="text-[10px] uppercase tracking-wide text-muted">Request ID</dt>
                <dd className="mono mt-0.5">{request.code}</dd>
              </div>
              <div>
                <dt className="text-[10px] uppercase tracking-wide text-muted">Parcel ID</dt>
                <dd className="mono mt-0.5">{request.parcel.code}</dd>
              </div>
              <div>
                <dt className="text-[10px] uppercase tracking-wide text-muted">Last updated</dt>
                <dd className="mt-0.5">{formatDateTime(request.updated_at)}</dd>
              </div>
              <div>
                <dt className="text-[10px] uppercase tracking-wide text-muted">Service</dt>
                <dd className="mt-0.5">{serviceLabel(request.type)}</dd>
              </div>
            </dl>
            <Link href="/customer/requests" className="btn btn-secondary btn-sm mt-4 w-full">Back to my requests</Link>
          </Card>
        </div>
      </div>
    </div>
  );
}
