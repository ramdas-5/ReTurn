"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";

import RouteMap from "@/components/RouteMap";
import { StatusBadge } from "@/components/Status";
import { Card, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatDateTime, formatKm } from "@/lib/format";
import type { BatchDetail } from "@/lib/types";

export default function DriverBatchPage() {
  const params = useParams<{ id: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["driver-batch", params.id],
    queryFn: () => apiGet<BatchDetail>(`/driver/batches/${params.id}`),
  });

  if (isLoading) return <p className="text-sm text-muted">Loading batch…</p>;
  if (error) return <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-[#8c2f2f]">{(error as Error).message}</p>;
  if (!data) return null;
  const plan = data.route_plan;
  const stops = plan?.stops ?? [];

  return (
    <div>
      <PageHeader eyebrow="Active route" title={data.batch_number} back={{ href: "/driver/batches", label: "All batches" }} actions={<StatusBadge status={data.status} />} description={`${data.order_count} orders · ${stops.length} stops · ${formatKm(data.distance_km)} (${data.distance_source})`} />
      <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        <Card>
          <RouteMap
            stops={stops.map((stop) => ({
              id: stop.id,
              code: stop.order?.order_number,
              label: stop.label,
              area: stop.address.area,
              latitude: stop.address.latitude ?? 0,
              longitude: stop.address.longitude ?? 0,
              kind: stop.kind === "delivery" ? "dropoff" : "pickup",
              sequence: stop.sequence,
              status: stop.status,
            }))}
            geometry={plan?.geometry ?? data.geometry}
            geometrySource={data.distance_source}
            height="390px"
          />
          <p className="mt-2 text-xs text-muted">Route data source: {data.distance_source}. {data.distance_source === "estimated" ? "Connectors are illustrative, not road navigation." : "Road geometry supplied by OSRM."}</p>
        </Card>
        <div className="space-y-3">
          {stops.map((stop) => (
            <Card key={stop.id} className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-muted">Stop {stop.sequence} · {stop.kind}</p>
                <p className="mt-1 font-semibold">{stop.order?.order_number ?? stop.label}</p>
                <p className="text-[13px] text-muted">{stop.address.address_line}, {stop.address.area}</p>
                <p className="mt-1 text-xs text-muted">{formatDateTime(stop.planned_arrival)}</p>
                {stop.order?.id ? <Link href={`/driver/assignments/${stop.order.id}`} className="link mt-1 inline-block text-xs">Open order</Link> : null}
              </div>
              <StatusBadge status={stop.status} />
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
