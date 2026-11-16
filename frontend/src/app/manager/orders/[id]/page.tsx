"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";

import ManagerOrderActions from "@/components/ManagerOrderActions";
import Timeline from "@/components/Timeline";
import { ServiceBadge, StatusBadge } from "@/components/Status";
import { Card, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatDateTime, formatWeight, formatWindow } from "@/lib/format";
import type { OrderDetail } from "@/lib/types";

export default function ManagerOrderPage() {
  const params = useParams<{ id: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["manager-order", params.id],
    queryFn: () => apiGet<OrderDetail>(`/manager/orders/${params.id}`),
  });

  if (isLoading) return <p className="text-sm text-muted">Loading order…</p>;
  if (error) return <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-[#8c2f2f]">{(error as Error).message}</p>;
  if (!data) return null;

  return (
    <div>
      <PageHeader eyebrow={data.order_number} title={data.service_type === "return" ? "Product return" : "Parcel delivery"} back={{ href: "/manager/orders", label: "Order queue" }} actions={<StatusBadge status={data.status} />} description={`${data.pickup.area} → ${data.delivery.area} · ${formatWeight(data.parcel.weight_kg)}`} />
      <div className="grid gap-6 lg:grid-cols-[1.35fr_1fr]">
        <div className="space-y-5">
          <Card>
            <div className="flex flex-wrap items-center gap-2"><ServiceBadge type={data.service_type} /><span className="text-xs text-muted">Created {formatDateTime(data.created_at)}</span>{data.consumer ? <span className="chip chip-neutral">{data.consumer.full_name}</span> : null}</div>
            <div className="mt-4 grid gap-5 sm:grid-cols-2">
              <div><p className="eyebrow">Pickup</p><p className="mt-1 text-sm font-semibold">{data.pickup_address?.contact_name} · {data.pickup_address?.contact_phone}</p><p className="text-[13px] text-muted">{data.pickup_address?.address_line}, {data.pickup_address?.area}</p><p className="mt-1 text-xs text-muted">{formatWindow(data.pickup.window_start, data.pickup.window_end)}</p></div>
              <div><p className="eyebrow">Delivery</p><p className="mt-1 text-sm font-semibold">{data.delivery_address?.contact_name} · {data.delivery_address?.contact_phone}</p><p className="text-[13px] text-muted">{data.delivery_address?.address_line}, {data.delivery_address?.area}</p><p className="mt-1 text-xs text-muted">Deadline {formatDateTime(data.delivery.deadline)}</p></div>
            </div>
            <div className="divider" />
            <p className="text-[13px]">{data.parcel.name} · {data.parcel.quantity} × {formatWeight(data.parcel.weight_kg)} · {data.parcel.is_fragile ? "fragile" : "standard"}</p>
            {data.return_request ? <p className="mt-2 rounded-control bg-surface-muted p-2 text-xs">Return to {data.return_request.merchant_name ?? data.return_request.destination_type} · {data.return_request.reason}</p> : null}
            {data.service_notes ? <p className="mt-2 text-sm text-muted">Notes: {data.service_notes}</p> : null}
            {data.batch ? <p className="mt-2 text-sm">Batch: <Link href={`/manager/batches/${data.batch.id}`} className="link">{data.batch.batch_number}</Link> ({data.batch.status_label})</p> : null}
          </Card>
          <ManagerOrderActions orderId={data.id} status={data.status} suggestions={data.suggestions ?? []} />
        </div>
        <div className="space-y-5">
          <Card><h2 className="section-title">Status history</h2><div className="mt-3"><Timeline events={data.status_history} /></div></Card>
          <Card>
            <h2 className="section-title">Assignment history</h2>
            {data.assignment_history.length === 0 ? <p className="mt-2 text-sm text-muted">No assignments yet.</p> : (
              <ul className="mt-3 space-y-2 text-sm">
                {data.assignment_history.map((row) => <li key={row.id} className="flex justify-between gap-2 border-b pb-2 last:border-0"><span>{row.driver?.full_name ?? "Driver"} · {row.status}</span><span className="text-xs text-muted">{formatDateTime(row.assigned_at)}</span></li>)}
              </ul>
            )}
          </Card>
          {data.pickup_proof || data.delivery_proof ? (
            <Card>
              <h2 className="section-title">Proof</h2>
              {[data.pickup_proof, data.delivery_proof].filter(Boolean).map((proof) => proof?.image_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img key={proof.id} src={proof.image_url} alt={`${proof.kind} proof`} className="mt-2 max-h-44 rounded-control border object-contain" />
              ) : null)}
            </Card>
          ) : null}
        </div>
      </div>
    </div>
  );
}
