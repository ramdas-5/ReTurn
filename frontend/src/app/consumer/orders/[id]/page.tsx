"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, MapPin, Package, Truck } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import ConsumerOrderPanel from "@/components/ConsumerOrderPanel";
import Timeline from "@/components/Timeline";
import { ServiceBadge, StatusBadge } from "@/components/Status";
import { Card, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatDateTime, formatWeight, formatWindow } from "@/lib/format";
import type { OrderDetail } from "@/lib/types";

function ProofImage({ url, label }: { url: string | null; label: string }) {
  if (!url) return <p className="text-sm text-muted">No image recorded.</p>;
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={url} alt={label} className="mt-2 max-h-56 rounded-control border object-contain" />
  );
}

export default function ConsumerOrderDetailPage() {
  const params = useParams<{ id: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["consumer-order", params.id],
    queryFn: () => apiGet<OrderDetail>(`/orders/${params.id}`),
  });

  if (isLoading) return <p className="text-sm text-muted">Loading order…</p>;
  if (error) return <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-[#8c2f2f]">{(error as Error).message}</p>;
  if (!data) return null;

  return (
    <div>
      <PageHeader
        eyebrow={data.order_number}
        title={data.service_type === "return" ? "Product return" : "Parcel delivery"}
        description={`${data.pickup.area ?? "Pickup"} → ${data.delivery.area ?? "Destination"}`}
        back={{ href: "/consumer/orders", label: "All orders" }}
        actions={<StatusBadge status={data.status} />}
      />

      <div className="grid gap-6 lg:grid-cols-[1.35fr_1fr]">
        <div className="space-y-5">
          <Card>
            <div className="flex flex-wrap items-center gap-2">
              <ServiceBadge type={data.service_type} />
              <span className="text-xs text-muted">Created {formatDateTime(data.created_at)}</span>
            </div>
            <div className="mt-4 grid gap-5 sm:grid-cols-2">
              <div>
                <p className="eyebrow">Pickup</p>
                <p className="mt-1 text-sm font-semibold">{data.pickup_address?.contact_name}</p>
                <p className="text-[13px] leading-5 text-muted">{data.pickup_address?.address_line}, {data.pickup_address?.area}</p>
                <p className="mt-1 text-xs text-muted">{formatWindow(data.pickup.window_start, data.pickup.window_end)}</p>
              </div>
              <div>
                <p className="eyebrow">Delivery</p>
                <p className="mt-1 text-sm font-semibold">{data.delivery_address?.contact_name}</p>
                <p className="text-[13px] leading-5 text-muted">{data.delivery_address?.address_line}, {data.delivery_address?.area}</p>
                <p className="mt-1 text-xs text-muted">Deadline {formatDateTime(data.delivery.deadline)}</p>
              </div>
            </div>
            <div className="divider" />
            <div className="flex flex-wrap gap-x-8 gap-y-3 text-[13px]">
              <span><Package size={14} className="mr-1 inline" aria-hidden /> {data.parcel.name}</span>
              <span>{formatWeight(data.parcel.weight_kg)}</span>
              <span>{data.parcel.is_fragile ? "Fragile" : "Standard handling"}</span>
              {data.parcel.photo_exception_reason ? <span className="text-[#8a5a12]">Photo exception recorded</span> : null}
            </div>
            {data.return_request ? (
              <div className="mt-4 rounded-control bg-surface-muted p-3 text-[13px]">
                <p className="font-semibold">Return: {data.return_request.product_name}</p>
                <p className="text-muted">{data.return_request.reason}</p>
                <p className="mt-1 text-xs text-muted">Destination: {data.return_request.merchant_name ?? data.return_request.destination_type}</p>
              </div>
            ) : null}
          </Card>

          <Card>
            <h2 className="section-title">Parcel tracking</h2>
            <div className="mt-4"><Timeline events={data.status_history} /></div>
          </Card>

          {data.delivery_proof || data.pickup_proof ? (
            <Card>
              <h2 className="section-title">Recorded proof</h2>
              <div className="mt-3 grid gap-4 sm:grid-cols-2">
                {data.pickup_proof ? <div><p className="eyebrow">Pickup proof</p><ProofImage url={data.pickup_proof.image_url} label="Pickup proof" /></div> : null}
                {data.delivery_proof ? <div><p className="eyebrow">Delivery proof</p><ProofImage url={data.delivery_proof.image_url} label="Delivery proof" /><p className="mt-1 text-xs text-muted">{data.delivery_proof.status}</p></div> : null}
              </div>
            </Card>
          ) : null}

          <ConsumerOrderPanel orderId={data.id} status={data.status} />
        </div>

        <div className="space-y-5">
          <Card>
            <h2 className="section-title">Assignment</h2>
            {data.assignment?.driver ? (
              <div className="mt-3 text-sm">
                <p className="font-semibold">{data.assignment.driver.full_name}</p>
                {data.assignment.driver.phone ? <p className="text-muted">{data.assignment.driver.phone}</p> : null}
                {data.assignment.vehicle ? <p className="mt-1 text-xs text-muted">{data.assignment.vehicle.vehicle_type} · {data.assignment.vehicle.registration_number}</p> : null}
              </div>
            ) : (
              <p className="mt-2 text-sm text-muted">No driver assigned yet. A manager will review and assign compatible work.</p>
            )}
            {data.batch ? (
              <div className="mt-4 rounded-control bg-surface-muted p-3 text-[13px]">
                <p className="font-medium">{data.batch.batch_number}</p>
                <p className="text-muted">{data.batch.status_label}</p>
                {data.assignment?.driver?.phone ? <a className="link mt-2 inline-block text-xs" href={`tel:${data.assignment.driver.phone}`}>Call driver</a> : null}
              </div>
            ) : null}
          </Card>

          <Card>
            <h2 className="section-title">Parcel photographs</h2>
            {data.images.length === 0 ? <p className="mt-2 text-sm text-muted">No photograph on file.</p> : (
              <div className="mt-3 space-y-3">
                {data.images.map((image) => <ProofImage key={image.id} url={image.url} label="Parcel exterior" />)}
              </div>
            )}
          </Card>

          <Card>
            <h2 className="section-title">Service notes</h2>
            <p className="mt-2 text-sm leading-6 text-muted">{data.service_notes || "No additional notes."}</p>
            <div className="divider" />
            <div className="flex items-center gap-2 text-xs text-muted"><MapPin size={14} aria-hidden /> Address details are shared only with the assigned driver.</div>
          </Card>

          <Link href={`/consumer/orders/${data.id}/tracking`} className="btn btn-secondary w-full">
            <Truck size={15} aria-hidden /> Open dedicated tracking view
          </Link>
          <Link href="/consumer/support" className="btn btn-ghost w-full"><ArrowLeft size={15} aria-hidden /> Get help</Link>
        </div>
      </div>
    </div>
  );
}
