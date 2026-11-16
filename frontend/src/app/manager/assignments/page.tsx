"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import OrderList from "@/components/OrderList";
import { PageHeader } from "@/components/ui";
import { apiGetList } from "@/lib/api";
import type { OrderSummary } from "@/lib/types";

export default function PendingAssignmentsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["manager-orders", "pending-assignment"],
    queryFn: () => apiGetList<OrderSummary>("/manager/orders?status=awaiting_assignment&per_page=100"),
  });

  return (
    <div>
      <PageHeader eyebrow="Pending assignments" title="Approved orders without a driver" description="Assign individual work or create a shared batch. Capacity, duty and service area are always revalidated." actions={<Link href="/manager/matching" className="btn btn-secondary">Scan active routes</Link>} />
      {isLoading ? <p className="text-sm text-muted">Loading queue…</p> : null}
      {error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-[#8c2f2f]">{(error as Error).message}</p> : null}
      {data ? <OrderList orders={data.data} hrefBase="/manager/orders" showConsumer emptyTitle="Nothing waiting for assignment" emptyDescription="Approved orders will appear here." /> : null}
    </div>
  );
}
