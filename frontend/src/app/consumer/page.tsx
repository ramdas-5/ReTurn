"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, Clock3, MapPin, Package, RotateCcw } from "lucide-react";
import Link from "next/link";

import OrderList from "@/components/OrderList";
import { Card, PageHeader, StatCard } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import type { ConsumerSummary } from "@/lib/types";

export default function ConsumerDashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["consumer-summary"],
    queryFn: () => apiGet<ConsumerSummary>("/consumer/summary"),
  });

  return (
    <div>
      <PageHeader
        eyebrow="Consumer workspace"
        title="Your deliveries, in one calm place"
        description="Send a parcel, return a product, and follow every parcel-level update. A manager reviews each order before a driver is committed."
        actions={
          <>
            <Link href="/consumer/parcels/new" className="btn btn-primary">Send a parcel</Link>
            <Link href="/consumer/returns/new" className="btn btn-secondary">Return a product</Link>
          </>
        }
      />

      {isLoading ? <p className="text-sm text-muted">Loading your dashboard…</p> : null}
      {error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-red-ink">{(error as Error).message}</p> : null}

      {data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Active orders" value={data.counts.in_progress + data.counts.awaiting_assignment + data.counts.awaiting_review} hint="In review, matching or on the road" icon={<Clock3 size={17} aria-hidden />} tone="amber" />
            <StatCard label="Delivered" value={data.counts.delivered} hint="Completed with recorded proof" icon={<CheckCircle2 size={17} aria-hidden />} tone="accent" />
            <StatCard label="Returns" value={data.counts.returns} hint="Reverse-logistics requests" icon={<RotateCcw size={17} aria-hidden />} tone="blue" />
            <StatCard label="Saved addresses" value={data.profile.saved_addresses} hint={data.profile.has_business_profile ? "Business profile active" : "Individual account"} icon={<MapPin size={17} aria-hidden />} />
          </div>

          <div className="mt-8 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
            <section>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="section-title">Active orders</h2>
                <Link href="/consumer/orders" className="link inline-flex items-center gap-1 text-sm">All orders <ArrowRight size={14} aria-hidden /></Link>
              </div>
              <OrderList orders={data.active_orders} hrefBase="/consumer/orders" emptyTitle="Nothing on the road right now" emptyDescription="Start a parcel or return and it will appear here." />
            </section>

            <div className="space-y-6">
              <Card>
                <div className="flex items-center justify-between">
                  <h2 className="section-title">Notifications</h2>
                  <Link href="/consumer/notifications" className="link text-sm">View all</Link>
                </div>
                {data.notifications.latest.length === 0 ? (
                  <p className="mt-3 text-sm text-muted">No notifications yet.</p>
                ) : (
                  <ul className="mt-3 space-y-3">
                    {data.notifications.latest.map((item) => (
                      <li key={item.id} className="border-b pb-3 last:border-0 last:pb-0">
                        <p className="text-sm font-semibold">{item.title}</p>
                        <p className="mt-0.5 text-xs leading-5 text-muted">{item.body}</p>
                        <p className="mt-1 text-2xs uppercase tracking-wide text-muted">{relativeTime(item.created_at)}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>

              <Card>
                <h2 className="section-title">Quick actions</h2>
                <div className="mt-3 space-y-2">
                  <Link href="/consumer/availability" className="btn btn-secondary w-full justify-start">Check service availability</Link>
                  <Link href="/consumer/addresses" className="btn btn-secondary w-full justify-start">Saved addresses</Link>
                  <Link href="/consumer/business" className="btn btn-secondary w-full justify-start">Business profile</Link>
                  <Link href="/consumer/support" className="btn btn-secondary w-full justify-start">Support & issues</Link>
                </div>
                <p className="mt-4 flex items-start gap-2 text-xs leading-5 text-muted">
                  <Package size={14} className="mt-0.5 shrink-0" aria-hidden />
                  A driver is only committed after manager review. Availability shown before booking is an honest estimate.
                </p>
              </Card>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
