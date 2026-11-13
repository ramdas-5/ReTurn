import { AlertTriangle, Package, UserRound } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import IssueForm from "@/components/actions/IssueForm";
import ParcelActions from "@/components/actions/ParcelActions";
import { ServiceBadge, StatusBadge } from "@/components/Status";
import Timeline from "@/components/Timeline";
import { Callout, Card, PageHeader } from "@/components/ui";
import { formatDateTime, formatWeight } from "@/lib/format";
import { requireUser, serverFetch } from "@/lib/server";
import type { Batch } from "@/lib/types";

export const metadata = { title: "Parcel statuses" };

export default async function PartnerParcelsPage({
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
  const canUpdate = batch.status === "in_progress";
  const contactsVisible = ["accepted", "in_progress", "completed"].includes(batch.status);

  return (
    <div>
      <PageHeader
        back={{ href: `/partner/batches/${batch.id}`, label: "Batch details" }}
        eyebrow="Parcel execution"
        title="Parcel statuses"
        description="Each parcel is updated independently through legal transitions. A delivered state can never be recorded before pickup."
        actions={
          <>
            <StatusBadge status={batch.status} />
            <Link href={`/partner/batches/${batch.id}/route`} className="btn btn-secondary">View route</Link>
          </>
        }
      />

      {!canUpdate ? (
        <div className="mb-5">
          <Callout tone="warning" title="Route not started">
            {batch.status === "accepted"
              ? "Start the route from the batch actions below before updating parcels."
              : "Parcel updates are only available while this batch is in progress."}
          </Callout>
        </div>
      ) : null}

      <div className="space-y-4">
        {batch.requests.map((request) => (
          <Card key={request.id} className="card-pad">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="mono text-[12px] font-medium">{request.code}</span>
                  <ServiceBadge type={request.type} />
                  <StatusBadge status={request.parcel.status} />
                </div>
                <p className="mt-2 flex items-center gap-1.5 text-sm font-medium">
                  <Package size={15} className="text-muted" aria-hidden />
                  {request.parcel.description} · {formatWeight(request.parcel.weight_kg)} · {request.parcel.volume_m3.toFixed(3)} m³
                </p>
                <p className="mt-1 text-[12px] text-muted">
                  {request.parcel.handling.length ? `Handling: ${request.parcel.handling.join(", ")}` : "No special handling"}
                </p>
              </div>
              <ParcelActions
                parcelId={request.parcel.id}
                status={request.parcel.status}
                code={request.parcel.code}
                disabled={!canUpdate}
              />
            </div>

            <div className="mt-4 grid gap-4 border-t pt-4 sm:grid-cols-2">
              <div className="text-[12px] leading-5">
                <p className="text-[10px] uppercase tracking-wide text-muted">Pickup</p>
                <p className="mt-0.5 font-medium">{request.pickup.area}</p>
                <p className="text-muted">
                  {contactsVisible ? request.pickup.address_line : "Address hidden until acceptance"}
                </p>
                {contactsVisible ? (
                  <p className="mt-1 flex items-center gap-1.5 text-muted">
                    <UserRound size={12} aria-hidden /> {request.customer?.name}
                    {request.customer?.phone ? ` · ${request.customer.phone}` : ""}
                  </p>
                ) : null}
              </div>
              <div className="text-[12px] leading-5">
                <p className="text-[10px] uppercase tracking-wide text-muted">
                  {request.type === "return" ? "Authorised return destination" : "Recipient"}
                </p>
                <p className="mt-0.5 font-medium">
                  {request.type === "return"
                    ? request.return_detail?.authorized_hub_name ?? request.destination.label
                    : request.recipient?.name ?? "Recipient"}
                </p>
                <p className="text-muted">
                  {contactsVisible ? request.destination.address_line : "Address hidden until acceptance"}
                </p>
                {request.type === "parcel" && contactsVisible ? (
                  <p className="mt-1 text-muted">
                    Instructions: {request.recipient?.instructions || "None recorded"}
                  </p>
                ) : null}
              </div>
            </div>

            {request.parcel.status === "failed" ? (
              <div className="mt-4">
                <Callout tone="danger" title="Failed parcel">
                  {request.failure_reason ?? "An issue is open for the dispatch team."} Tracking history is preserved.
                </Callout>
              </div>
            ) : null}

            <details className="mt-4 rounded-control border bg-surface-muted px-4 py-3">
              <summary className="cursor-pointer text-[12px] font-medium">
                Parcel timeline & report an issue
              </summary>
              <div className="mt-3">
                <Timeline events={request.tracking ?? []} emptyMessage="No tracking events loaded for this parcel yet." />
              </div>
              <div className="mt-4 border-t pt-3">
                <p className="flex items-center gap-1.5 text-[12px] font-medium text-[#8a5a12]">
                  <AlertTriangle size={14} aria-hidden /> Report an operational issue
                </p>
                <IssueForm requestId={request.id} compact />
              </div>
            </details>
            <p className="mt-2 text-[10px] text-muted">
              Request last updated {formatDateTime(request.updated_at)}
            </p>
          </Card>
        ))}
      </div>
    </div>
  );
}
