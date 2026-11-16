"use client";

import { useQuery } from "@tanstack/react-query";
import { Building2, PackageCheck, ShieldCheck, Truck, Users } from "lucide-react";
import Link from "next/link";

import OrderList from "@/components/OrderList";
import Timeline from "@/components/Timeline";
import { PageHeader, StatCard } from "@/components/ui";
import { apiGet, apiGetList } from "@/lib/api";
import type { AdminOverview, AuditLog, OrderSummary } from "@/lib/types";

export default function AdminDashboard() {
  const summary = useQuery({ queryKey: ["admin-summary"], queryFn: () => apiGet<AdminOverview>("/admin/summary") });
  const recent = useQuery({ queryKey: ["admin-orders", "recent"], queryFn: () => apiGetList<OrderSummary>("/admin/orders?per_page=6") });
  const audit = useQuery({ queryKey: ["admin-audit", "recent"], queryFn: () => apiGetList<AuditLog>("/admin/audit?per_page=6") });

  const data = summary.data;
  return (
    <div>
      <PageHeader
        eyebrow="Platform control"
        title="ReTurn operations overview"
        description="Every figure below is counted from stored accounts, orders, batches and fleet rows. Suspensions and verification actions are audited."
        actions={<><Link href="/admin/analytics" className="btn btn-secondary">Analytics</Link><Link href="/admin/operations" className="btn btn-primary">Live operations</Link></>}
      />
      {summary.isLoading ? <p className="text-sm text-muted">Loading platform summary…</p> : null}
      {summary.error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-[#8c2f2f]">{(summary.error as Error).message}</p> : null}
      {data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Active orders" value={data.orders.active} hint={`${data.orders.today} created today`} icon={<PackageCheck size={17} aria-hidden />} tone="amber" />
            <StatCard label="Delivered" value={data.orders.delivered} hint={`${data.orders.delivered_today} today`} icon={<CheckIcon />} tone="accent" />
            <StatCard label="Drivers" value={data.fleet.drivers} hint={`${data.fleet.on_duty} on duty · ${data.fleet.verified_drivers} verified`} icon={<Truck size={17} aria-hidden />} tone="blue" />
            <StatCard label="Accounts" value={data.accounts.consumers + data.accounts.managers + data.accounts.drivers + data.accounts.admins} hint={`${data.accounts.suspended} suspended · ${data.accounts.pending_activation} pending activation`} icon={<Users size={17} aria-hidden />} />
          </div>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Business accounts" value={data.accounts.business_consumers} icon={<Building2 size={17} aria-hidden />} />
            <StatCard label="Proofs pending" value={data.proofs.pending} hint={`${data.proofs.total} total captured`} icon={<ShieldCheck size={17} aria-hidden />} tone="amber" />
            <StatCard label="Open exceptions" value={data.exceptions.open} hint={`${data.exceptions.resolved} resolved`} tone="red" />
            <StatCard label="Batches active" value={data.batches.active} hint={`${data.batches.total} total`} />
          </div>
          <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
            <section>
              <div className="mb-3 flex items-center justify-between"><h2 className="section-title">Recent orders</h2><Link href="/admin/orders" className="link text-sm">All orders</Link></div>
              <OrderList orders={recent.data?.data ?? []} hrefBase="/admin/orders" showConsumer />
            </section>
            <section>
              <div className="mb-3 flex items-center justify-between"><h2 className="section-title">Audit trail</h2><Link href="/admin/audit" className="link text-sm">Full log</Link></div>
              <div className="card">
                <ul className="divide-y">
                  {audit.data?.data.map((row) => <li key={row.id} className="px-4 py-3"><p className="text-[13px] font-medium">{row.summary}</p><p className="mt-1 text-[11px] text-muted">{row.action} · {row.actor?.full_name ?? "System"}</p></li>)}
                  {audit.data && audit.data.data.length === 0 ? <li className="px-4 py-4 text-sm text-muted">No audit entries yet.</li> : null}
                </ul>
              </div>
              <p className="mt-3 text-xs leading-5 text-muted">{data.disclaimer}</p>
            </section>
          </div>
        </>
      ) : null}
    </div>
  );
}

function CheckIcon() {
  return <ShieldCheck size={17} aria-hidden />;
}
