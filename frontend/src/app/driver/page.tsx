"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Package, Truck } from "lucide-react";
import Link from "next/link";

import DriverDutyControls from "@/components/DriverDutyControls";
import OrderList from "@/components/OrderList";
import { EmptyState, PageHeader, StatCard } from "@/components/ui";
import { apiGet, apiGetList } from "@/lib/api";
import { formatDateTime, formatKm, formatWeight } from "@/lib/format";
import type { DriverSummary, OrderSummary } from "@/lib/types";

export default function DriverDashboard() {
  const summary = useQuery({
    queryKey: ["driver-summary"],
    queryFn: () => apiGet<DriverSummary>("/driver/summary"),
  });
  const assignments = useQuery({
    queryKey: ["driver-assignments", "active"],
    queryFn: () => apiGetList<OrderSummary>("/driver/assignments?window=active"),
  });

  const data = summary.data;
  const next = data?.next_stop as Record<string, any> | null | undefined;

  return (
    <div>
      <PageHeader
        eyebrow="Driver field app"
        title="Today's route"
        description="Accept only work assigned to you, keep your duty heartbeat fresh, and complete deliveries with valid captured proof."
        actions={<Link href="/driver/duty" className="btn btn-secondary">Duty & availability</Link>}
      />
      {summary.isLoading ? <p className="text-sm text-muted">Loading dashboard…</p> : null}
      {summary.error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-red-ink">{(summary.error as Error).message}</p> : null}
      {data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Assigned orders" value={data.counts.assigned_orders} hint={`${data.counts.pending_pickups} pickups · ${data.counts.out_for_delivery} deliveries`} icon={<Package size={17} aria-hidden />} />
            <StatCard label="Completed today" value={data.counts.completed_today} hint={`${data.counts.completed_total} lifetime`} icon={<CheckCircle2 size={17} aria-hidden />} tone="accent" />
            <StatCard label="Vehicle load" value={formatWeight(data.vehicle_load.weight_kg)} hint={data.vehicle_load.max_weight_kg ? `of ${data.vehicle_load.max_weight_kg} kg capacity` : "No active vehicle"} icon={<Truck size={17} aria-hidden />} tone="blue" />
            <StatCard label="Route distance" value={data.today.route_distance_km != null ? formatKm(data.today.route_distance_km) : "—"} hint={data.today.active_batch ? data.today.active_batch.batch_number : "No active batch"} />
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-[1.35fr_1fr]">
            <section>
              <h2 className="section-title mb-3">Active assignments</h2>
              <OrderList
                orders={assignments.data?.data ?? []}
                hrefBase="/driver/assignments"
                emptyTitle="No active work"
                emptyDescription="Assignments appear after a manager dispatches an order to you."
              />
              <div className="mt-4">
                <Link href="/driver/assignments" className="link text-sm">Open all assignments →</Link>
              </div>
            </section>
            <div className="space-y-5">
              <DriverDutyControls compact />
              <div className="card card-pad">
                <h2 className="section-title">Next stop</h2>
                {next ? (
                  <div className="mt-2 text-sm">
                    <p className="font-semibold">{String(next.kind ?? "stop")} · {next.order?.order_number ?? ""}</p>
                    <p className="text-muted">{next.address?.area ?? next.address?.address_line ?? ""}</p>
                    <p className="mt-1 text-xs text-muted">{formatDateTime(next.planned_at ?? next.planned_arrival)}</p>
                    {next.order?.id ? <Link href={`/driver/assignments/${next.order.id}`} className="btn btn-primary btn-sm mt-3">Open stop</Link> : null}
                  </div>
                ) : (
                  <EmptyState title="No next stop" description="The route will populate after a batch is assigned." />
                )}
              </div>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
