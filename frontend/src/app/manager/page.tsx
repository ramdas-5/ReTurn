"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ClipboardList, Truck, Users } from "lucide-react";
import Link from "next/link";

import OrderList from "@/components/OrderList";
import { PageHeader, StatCard } from "@/components/ui";
import { apiGet } from "@/lib/api";
import type { ManagerSummary } from "@/lib/types";

export default function ManagerDashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["manager-summary"],
    queryFn: () => apiGet<ManagerSummary>("/manager/summary"),
  });

  return (
    <div>
      <PageHeader
        eyebrow="Operations desk"
        title="Dispatch control"
        description="Review new orders, assign compatible drivers, and watch real duty and route activity. All capacity and service-area rules are revalidated server-side."
        actions={<><Link href="/manager/orders" className="btn btn-primary">Order queue</Link><Link href="/manager/matching" className="btn btn-secondary">Smart matching</Link></>}
      />
      {isLoading ? <p className="text-sm text-muted">Loading operations summary…</p> : null}
      {error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-[#8c2f2f]">{(error as Error).message}</p> : null}
      {data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Orders to review" value={data.orders.pending} hint={`${data.orders.new_today} new today`} icon={<ClipboardList size={17} aria-hidden />} tone="amber" />
            <StatCard label="Awaiting assignment" value={data.orders.awaiting_assignment} hint={`${data.orders.assigned} assigned · ${data.orders.in_progress} in custody`} icon={<Truck size={17} aria-hidden />} />
            <StatCard label="Drivers on duty" value={data.drivers.on_duty} hint={`${data.drivers.available} available · ${data.drivers.live} live location`} icon={<Users size={17} aria-hidden />} tone="blue" />
            <StatCard label="Needs attention" value={data.orders.needs_attention} hint={`${data.exceptions.open} open exceptions · ${data.orders.delayed} delayed`} icon={<AlertTriangle size={17} aria-hidden />} tone="red" />
          </div>
          <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
            <section>
              <div className="mb-3 flex items-center justify-between"><h2 className="section-title">Attention queue</h2><Link href="/manager/orders" className="link text-sm">All orders</Link></div>
              <OrderList orders={data.attention_orders} hrefBase="/manager/orders" showConsumer emptyTitle="No urgent orders" emptyDescription="Orders needing review or with problems will appear here." />
            </section>
            <div className="space-y-4">
              <div className="card card-pad">
                <h2 className="section-title">Capacity snapshot</h2>
                <dl className="mt-3 space-y-2 text-sm">
                  <div className="flex justify-between"><dt className="text-muted">Active batches</dt><dd className="font-semibold">{data.batches.active + data.batches.assigned}</dd></div>
                  <div className="flex justify-between"><dt className="text-muted">Delivered today</dt><dd className="font-semibold">{data.orders.delivered_today}</dd></div>
                  <div className="flex justify-between"><dt className="text-muted">Delivered total</dt><dd className="font-semibold">{data.orders.delivered_total}</dd></div>
                  <div className="flex justify-between"><dt className="text-muted">Failed orders</dt><dd className="font-semibold">{data.orders.failed}</dd></div>
                </dl>
              </div>
              <div className="card card-pad">
                <h2 className="section-title">Coverage</h2>
                <p className="mt-2 text-sm text-muted">{data.manager.service_areas.length ? data.manager.service_areas.join(", ") : "No service areas assigned. New orders outside coverage will escalate to administrators."}</p>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Link href="/manager/live" className="btn btn-secondary">Live tracking</Link>
                <Link href="/manager/proofs" className="btn btn-secondary">Proof audit</Link>
                <Link href="/manager/issues" className="btn btn-secondary">Delivery issues</Link>
                <Link href="/manager/drivers" className="btn btn-secondary">Drivers</Link>
              </div>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
