"use client";

import { useQuery } from "@tanstack/react-query";

import OrderList from "@/components/OrderList";
import { PageHeader } from "@/components/ui";
import { apiGetList } from "@/lib/api";
import type { OrderSummary } from "@/lib/types";

export default function DriverHistoryPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["driver-history"],
    queryFn: () => apiGetList<OrderSummary>("/driver/assignments?window=completed"),
  });

  return (
    <div>
      <PageHeader eyebrow="Delivery history" title="Completed work" description="Orders you completed, including any recorded delivery proof." />
      {isLoading ? <p className="text-sm text-muted">Loading history…</p> : null}
      {error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-red-ink">{(error as Error).message}</p> : null}
      {data ? <OrderList orders={data.data} hrefBase="/driver/assignments" emptyTitle="No completed deliveries yet" emptyDescription="Completed stops will appear here." /> : null}
    </div>
  );
}
