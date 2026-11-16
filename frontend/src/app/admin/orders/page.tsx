"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import OrderList from "@/components/OrderList";
import { PageHeader } from "@/components/ui";
import { apiGetList } from "@/lib/api";
import type { OrderSummary } from "@/lib/types";

export default function AdminOrdersPage() {
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-orders", status, q],
    queryFn: () => apiGetList<OrderSummary>(`/admin/orders?per_page=100${status ? `&status=${status}` : ""}${q ? `&q=${encodeURIComponent(q)}` : ""}`),
  });

  return (
    <div>
      <PageHeader eyebrow="All orders" title="Platform-wide order book" description="Global read access for administrators. Assignment and review actions are available on each order detail." />
      <div className="mb-4 flex flex-wrap gap-2">
        <select className="input !w-auto" value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">All statuses</option>
          <option value="submitted,pending_review">Review queue</option>
          <option value="awaiting_assignment">Awaiting assignment</option>
          <option value="assigned,pickup_scheduled,pickup_arrived">Assigned</option>
          <option value="picked_up,in_transit,out_for_delivery,delivery_proof_pending">In custody</option>
          <option value="delivered,returned">Completed</option>
          <option value="failed,cancelled">Problems</option>
        </select>
        <input className="input !w-auto" placeholder="Search order number" value={q} onChange={(event) => setQ(event.target.value)} />
      </div>
      {isLoading ? <p className="text-sm text-muted">Loading orders…</p> : null}
      {error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-[#8c2f2f]">{(error as Error).message}</p> : null}
      {data ? <OrderList orders={data.data} hrefBase="/admin/orders" showConsumer /> : null}
    </div>
  );
}
