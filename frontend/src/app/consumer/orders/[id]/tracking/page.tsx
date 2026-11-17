"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";

import Timeline from "@/components/Timeline";
import { StatusBadge } from "@/components/Status";
import { Card, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { OrderDetail } from "@/lib/types";

export default function TrackingPage() {
  const params = useParams<{ id: string }>();
  const { data, error } = useQuery({
    queryKey: ["consumer-order", params.id],
    queryFn: () => apiGet<OrderDetail>(`/orders/${params.id}`),
  });

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader eyebrow="Parcel tracking" title={data?.order_number ?? "Tracking"} description="Every status change is recorded by the platform, not simulated in the browser." back={{ href: `/consumer/orders/${params.id}`, label: "Order details" }} actions={data ? <StatusBadge status={data.status} /> : null} />
      {error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-red-ink">{(error as Error).message}</p> : null}
      {data ? (
        <div className="space-y-5">
          <Card>
            <div className="grid gap-3 sm:grid-cols-3">
              <div><p className="eyebrow">Pickup</p><p className="mt-1 text-sm">{data.pickup.area}</p></div>
              <div><p className="eyebrow">Destination</p><p className="mt-1 text-sm">{data.delivery.area}</p></div>
              <div><p className="eyebrow">Deadline</p><p className="mt-1 text-sm">{formatDateTime(data.delivery.deadline)}</p></div>
            </div>
          </Card>
          <Card><Timeline events={data.status_history} /></Card>
        </div>
      ) : null}
    </div>
  );
}
