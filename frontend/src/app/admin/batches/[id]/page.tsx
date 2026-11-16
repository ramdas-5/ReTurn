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

export default function AdminBatchDetailPage() {
  const params = useParams<{ id: string }>();
  const { data, isLoading, error } = useQuery({ queryKey: ["admin-batch", params.id], queryFn: () => apiGet<BatchDetail>(`/admin/batches/${params.id}`) });
  if (isLoading) return <p className="text-sm text-muted">Loading batch…</p>;
  if (error) return <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-[#8c2f2f]">{(error as Error).message}</p>;
  if (!data) return null;
  const stops = data.route_plan?.stops ?? [];
  return (
    <div>
      <PageHeader eyebrow="Batch detail" title={data.batch_number} back={{ href: "/admin/batches", label: "All batches" }} actions={<StatusBadge status={data.status} />} description={`${data.driver?.full_name ?? "Unassigned"} · ${formatKm(data.distance_km)} · ${data.distance_source}`} />
      <div className="grid gap-6 lg:grid-cols-[1.35fr_1fr]">
        <Card>
          <RouteMap stops={stops.map((stop) => ({ id: stop.id, code: stop.order?.order_number, label: stop.label, area: stop.address.area, latitude: stop.address.latitude ?? 0, longitude: stop.address.longitude ?? 0, kind: stop.kind === "delivery" ? "dropoff" : "pickup", sequence: stop.sequence, status: stop.status }))} geometry={data.route_plan?.geometry ?? data.geometry} geometrySource={data.distance_source} height="400px" />
          <p className="mt-2 text-xs text-muted">Route source {data.distance_source} · algorithm {data.algorithm}.</p>
        </Card>
        <div className="space-y-4">
          <Card><h2 className="section-title">Orders</h2><div className="mt-3 space-y-2">{data.orders.map((order) => <Link key={order.id} href={`/admin/orders/${order.id}`} className="flex items-center justify-between rounded-control border p-2 text-sm hover:bg-surface-muted"><span>{order.order_number}</span><StatusBadge status={order.status} /></Link>)}</div></Card>
          <Card><h2 className="section-title">Stops</h2><ol className="mt-2 space-y-2 text-sm">{stops.map((stop) => <li key={stop.id} className="border-b pb-2 last:border-0">{stop.sequence}. {stop.kind} · {stop.address.area}<span className="block text-xs text-muted">{formatDateTime(stop.planned_arrival)} · {stop.status}</span></li>)}</ol></Card>
        </div>
      </div>
    </div>
  );
}
