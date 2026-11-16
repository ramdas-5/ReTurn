"use client";

import { useQuery } from "@tanstack/react-query";

import OrderList from "@/components/OrderList";
import { PageHeader, StatCard } from "@/components/ui";
import { apiGetList } from "@/lib/api";
import type { OrderSummary } from "@/lib/types";

export default function ConsumerHistoryPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["consumer-history"],
    queryFn: () => apiGetList<OrderSummary>("/orders?window=completed"),
  });

  const orders = data?.data ?? [];

  return (
    <div>
      <PageHeader eyebrow="Order history" title="Completed deliveries and returns" description="Every completed order is listed with its recorded delivery evidence." />
      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <StatCard label="Completed" value={orders.length} hint="Delivered with proof where required" />
        <StatCard label="Returns completed" value={orders.filter((order) => order.service_type === "return").length} />
        <StatCard label="Parcels completed" value={orders.filter((order) => order.service_type === "parcel").length} />
      </div>
      {isLoading ? <p className="text-sm text-muted">Loading history…</p> : null}
      {error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-[#8c2f2f]">{(error as Error).message}</p> : null}
      {data ? <OrderList orders={orders} hrefBase="/consumer/orders" emptyTitle="No completed orders yet" emptyDescription="Completed deliveries and returns will be kept here." /> : null}
    </div>
  );
}
