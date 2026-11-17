"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import RouteMap from "@/components/RouteMap";
import { StatusBadge } from "@/components/Status";
import { Button, ErrorText } from "@/components/ui-bits";
import { Card, PageHeader } from "@/components/ui";
import { ApiError, apiGet, apiPost } from "@/lib/api";
import { formatDateTime, formatKm } from "@/lib/format";
import type { BatchDetail } from "@/lib/types";

type DriverRow = { driver: { id: number; full_name: string }; duty_label: string };

export default function ManagerBatchPage() {
  const params = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const { data } = useQuery({
    queryKey: ["manager-batch", params.id],
    queryFn: () => apiGet<BatchDetail>(`/manager/batches/${params.id}`),
  });
  const drivers = useQuery({ queryKey: ["manager-drivers"], queryFn: () => apiGet<Array<DriverRow>>("/manager/drivers") });

  async function action(key: string, path: string, body: unknown, note: string) {
    setBusy(key);
    setError(null);
    setMessage(null);
    try {
      await apiPost(path, body);
      setMessage(note);
      await queryClient.invalidateQueries({ queryKey: ["manager-batch", params.id] });
      await queryClient.invalidateQueries({ queryKey: ["manager-batches"] });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Action failed.");
    } finally {
      setBusy(null);
    }
  }

  if (!data) return <p className="text-sm text-muted">Loading batch…</p>;
  const stops = data.route_plan?.stops ?? [];

  return (
    <div>
      <PageHeader eyebrow="Batch detail" title={data.batch_number} back={{ href: "/manager/batches", label: "All batches" }} actions={<StatusBadge status={data.status} />} description={`${data.driver?.full_name ?? "Unassigned"} · ${data.order_count} orders · ${formatKm(data.distance_km)} (${data.distance_source})`} />
      {error ? <ErrorText>{error}</ErrorText> : null}
      {message ? <p className="mb-4 rounded-control bg-accent-soft px-3 py-2 text-sm text-accent-strong">{message}</p> : null}
      <div className="grid gap-6 lg:grid-cols-[1.35fr_1fr]">
        <div className="space-y-5">
          <Card>
            <RouteMap
              stops={stops.map((stop) => ({ id: stop.id, code: stop.order?.order_number, label: stop.label, area: stop.address.area, latitude: stop.address.latitude ?? 0, longitude: stop.address.longitude ?? 0, kind: stop.kind === "delivery" ? "dropoff" : "pickup", sequence: stop.sequence, status: stop.status }))}
              geometry={data.route_plan?.geometry ?? data.geometry}
              geometrySource={data.distance_source}
              height="380px"
            />
            <p className="mt-2 text-xs text-muted">{data.distance_source === "estimated" ? "Illustrative connectors — not road navigation." : "Road geometry supplied by OSRM."} · {data.algorithm}</p>
          </Card>
          <Card>
            <h2 className="section-title">Orders</h2>
            <div className="mt-3 space-y-2">
              {data.orders.map((order) => <Link key={order.id} href={`/manager/orders/${order.id}`} className="flex items-center justify-between rounded-control border p-3 text-sm hover:bg-surface-tint"><span>{order.order_number} · {order.pickup.area} → {order.delivery.area}</span><StatusBadge status={order.status} /></Link>)}
            </div>
          </Card>
        </div>
        <div className="space-y-5">
          <Card>
            <h2 className="section-title">Route stops</h2>
            <ol className="mt-3 space-y-2 text-sm">
              {stops.map((stop) => <li key={stop.id} className="border-b pb-2 last:border-0"><span className="font-semibold">{stop.sequence}. {stop.kind}</span> · {stop.address.area}<span className="block text-xs text-muted">{formatDateTime(stop.planned_arrival)} · {stop.status}</span></li>)}
            </ol>
          </Card>
          <Card>
            <h2 className="section-title">Reassign driver</h2>
            <form onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); void action("assign", `/manager/batches/${data.id}/assign-driver`, { driver_id: Number(form.get("driver_id")), reason: form.get("reason") }, "Batch reassigned."); }} className="mt-3 space-y-2">
              <select name="driver_id" className="input" required defaultValue=""><option value="" disabled>Choose a driver</option>{drivers.data?.map((row) => <option key={row.driver.id} value={row.driver.id}>{row.driver.full_name}</option>)}</select>
              <input name="reason" className="input" placeholder="Reason (5+ characters)" required minLength={5} />
              <Button type="submit" busy={busy === "assign"} className="btn btn-secondary">Reassign batch</Button>
            </form>
          </Card>
          <Card>
            <h2 className="section-title">Cancel batch</h2>
            <form onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); void action("cancel", `/manager/batches/${data.id}/cancel`, { reason: form.get("reason") }, "Batch cancelled."); }} className="mt-3 space-y-2">
              <input name="reason" className="input" placeholder="Cancellation reason (5+ characters)" required minLength={5} />
              <Button type="submit" busy={busy === "cancel"} className="btn btn-danger">Cancel batch</Button>
            </form>
          </Card>
        </div>
      </div>
    </div>
  );
}
