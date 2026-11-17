"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import OrderList from "@/components/OrderList";
import { PageHeader } from "@/components/ui";
import { apiGetList } from "@/lib/api";
import type { OrderSummary } from "@/lib/types";

const FILTERS = [
  { label: "Review queue", status: "submitted,pending_review" },
  { label: "Awaiting assignment", status: "awaiting_assignment" },
  { label: "Assigned", status: "assigned,pickup_scheduled,pickup_arrived" },
  { label: "In custody", status: "picked_up,in_transit,out_for_delivery,delivery_proof_pending" },
  { label: "Completed", status: "delivered,returned" },
  { label: "Problems", status: "failed,cancelled" },
  { label: "All", status: "" },
];

export default function ManagerOrdersPage() {
  const [status, setStatus] = useState(FILTERS[0].status);
  const [q, setQ] = useState("");
  const { data, isLoading, error } = useQuery({
    queryKey: ["manager-orders", status, q],
    queryFn: () => apiGetList<OrderSummary>(`/manager/orders?per_page=100${status ? `&status=${status}` : ""}${q ? `&q=${encodeURIComponent(q)}` : ""}`),
  });

  return (
    <div>
      <PageHeader eyebrow="Order management" title="Every order in your areas" description="Review submissions, assign drivers and follow execution. Use a specific order for assignment controls." actions={<Link href="/manager/batches/new" className="btn btn-primary">Create batch</Link>} />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {FILTERS.map((filter) => (
          <button key={filter.label} className={`chip ${status === filter.status ? "chip-teal" : "chip-neutral"}`} onClick={() => setStatus(filter.status)}>{filter.label}</button>
        ))}
        <input className="input !w-auto !py-1.5 text-sm" placeholder="Search order or consumer" value={q} onChange={(event) => setQ(event.target.value)} />
      </div>
      {isLoading ? <p className="text-sm text-muted">Loading orders…</p> : null}
      {error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-red-ink">{(error as Error).message}</p> : null}
      {data ? <OrderList orders={data.data} hrefBase="/manager/orders" showConsumer emptyTitle="No orders in this filter" emptyDescription="Try another queue or clear the search." /> : null}
    </div>
  );
}
