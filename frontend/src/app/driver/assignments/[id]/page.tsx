"use client";

import { useQuery } from "@tanstack/react-query";
import { MapPin, Navigation, Package } from "lucide-react";
import { useParams } from "next/navigation";

import DriverOrderActions from "@/components/DriverOrderActions";
import Timeline from "@/components/Timeline";
import { ServiceBadge, StatusBadge } from "@/components/Status";
import { Card, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatDateTime, formatWeight, formatWindow } from "@/lib/format";
import type { OrderDetail } from "@/lib/types";

export default function DriverStopPage() {
  const params = useParams<{ id: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["driver-assignment", params.id],
    queryFn: () => apiGet<OrderDetail>(`/orders/${params.id}`),
  });

  if (isLoading) return <p className="text-sm text-muted">Loading stop…</p>;
  if (error) return <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-[#8c2f2f]">{(error as Error).message}</p>;
  if (!data) return null;

  return (
    <div>
      <PageHeader
        eyebrow={data.order_number}
        title={`${data.pickup.area ?? "Pickup"} → ${data.delivery.area ?? "Destination"}`}
        back={{ href: "/driver/assignments", label: "All assignments" }}
        actions={<StatusBadge status={data.status} />}
      />
      <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        <div className="space-y-5">
          <Card>
            <div className="flex flex-wrap items-center gap-2"><ServiceBadge type={data.service_type} /><span className="text-xs text-muted">{formatDateTime(data.created_at)}</span></div>
            <div className="mt-4 grid gap-5 sm:grid-cols-2">
              <div>
                <p className="eyebrow">Pickup</p>
                <p className="mt-1 text-sm font-semibold">{data.pickup_address?.contact_name} · {data.pickup_address?.contact_phone}</p>
                <p className="text-[13px] text-muted">{data.pickup_address?.address_line}, {data.pickup_address?.area}</p>
                <p className="mt-1 text-xs text-muted">{formatWindow(data.pickup.window_start, data.pickup.window_end)}</p>
                {data.pickup_address?.latitude ? <a className="link mt-2 inline-flex items-center gap-1 text-xs" href={`https://www.google.com/maps/dir/?api=1&destination=${data.pickup_address.latitude},${data.pickup_address.longitude}`} target="_blank" rel="noreferrer"><Navigation size={13} aria-hidden /> Navigate to pickup</a> : null}
              </div>
              <div>
                <p className="eyebrow">Delivery</p>
                <p className="mt-1 text-sm font-semibold">{data.delivery_address?.contact_name} · {data.delivery_address?.contact_phone}</p>
                <p className="text-[13px] text-muted">{data.delivery_address?.address_line}, {data.delivery_address?.area}</p>
                <p className="mt-1 text-xs text-muted">Deadline {formatDateTime(data.delivery.deadline)}</p>
                {data.delivery_address?.latitude ? <a className="link mt-2 inline-flex items-center gap-1 text-xs" href={`https://www.google.com/maps/dir/?api=1&destination=${data.delivery_address.latitude},${data.delivery_address.longitude}`} target="_blank" rel="noreferrer"><MapPin size={13} aria-hidden /> Navigate to delivery</a> : null}
              </div>
            </div>
            <div className="divider" />
            <p className="flex flex-wrap gap-4 text-[13px]">
              <span className="inline-flex items-center gap-1"><Package size={14} aria-hidden /> {data.parcel.name}</span>
              <span>{formatWeight(data.parcel.weight_kg)}</span>
              <span>{data.parcel.is_fragile ? "Fragile" : "Standard"}</span>
            </p>
            {data.service_notes ? <p className="mt-2 text-sm text-muted">Notes: {data.service_notes}</p> : null}
          </Card>
          <DriverOrderActions orderId={data.id} status={data.status} />
        </div>
        <div className="space-y-5">
          <Card><h2 className="section-title">Timeline</h2><div className="mt-3"><Timeline events={data.status_history} /></div></Card>
          {data.images.length ? (
            <Card><h2 className="section-title">Sender photographs</h2><div className="mt-2 space-y-2">{data.images.map((image) => image.url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img key={image.id} src={image.url} alt="Parcel exterior" className="max-h-48 rounded-control border object-contain" />
            ) : null)}</div></Card>
          ) : null}
        </div>
      </div>
    </div>
  );
}
