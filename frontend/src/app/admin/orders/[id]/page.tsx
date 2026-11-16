"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";

import ManagerOrderActions from "@/components/ManagerOrderActions";
import Timeline from "@/components/Timeline";
import { ServiceBadge, StatusBadge } from "@/components/Status";
import { Card, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatDateTime, formatWindow } from "@/lib/format";
import type { OrderDetail } from "@/lib/types";

export default function AdminOrderDetailPage() {
  const params = useParams<{ id: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-order", params.id],
    queryFn: () => apiGet<OrderDetail>(`/admin/orders/${params.id}`),
  });

  if (isLoading) return <p className="text-sm text-muted">Loading order…</p>;
  if (error) return <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-[#8c2f2f]">{(error as Error).message}</p>;
  if (!data) return null;
  return (
    <div>
      <PageHeader eyebrow={data.order_number} title="Order detail" back={{ href: "/admin/orders", label: "All orders" }} actions={<StatusBadge status={data.status} />} description={`${data.consumer?.full_name ?? "Consumer"} · ${data.pickup.area} → ${data.delivery.area}`} />
      <div className="grid gap-6 lg:grid-cols-[1.35fr_1fr]">
        <div className="space-y-5">
          <Card>
            <div className="flex flex-wrap gap-2"><ServiceBadge type={data.service_type} /><span className="text-xs text-muted">Created {formatDateTime(data.created_at)}</span></div>
            <div className="mt-4 grid gap-4 sm:grid-cols-2 text-sm">
              <div><p className="eyebrow">Pickup</p><p className="mt-1 font-medium">{data.pickup_address?.address_line}, {data.pickup_address?.area}</p><p className="text-xs text-muted">{formatWindow(data.pickup.window_start, data.pickup.window_end)}</p></div>
              <div><p className="eyebrow">Delivery</p><p className="mt-1 font-medium">{data.delivery_address?.address_line}, {data.delivery_address?.area}</p><p className="text-xs text-muted">Deadline {formatDateTime(data.delivery.deadline)}</p></div>
            </div>
            <p className="mt-3 text-[13px]">{data.parcel.name} · {data.parcel.weight_kg} kg · {data.parcel.is_fragile ? "fragile" : "standard"}</p>
          </Card>
          <ManagerOrderActions orderId={data.id} status={data.status} suggestions={data.suggestions ?? []} />
        </div>
        <div className="space-y-4">
          <Card><h2 className="section-title">Timeline</h2><div className="mt-3"><Timeline events={data.status_history} /></div></Card>
          {data.consumer ? <Card><h2 className="section-title">Consumer</h2><p className="mt-2 text-sm">{data.consumer.full_name}</p><p className="text-xs text-muted">{data.consumer.email} · {data.consumer.phone}</p></Card> : null}
        </div>
      </div>
    </div>
  );
}
