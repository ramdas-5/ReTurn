"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import OrderList from "@/components/OrderList";
import { PageHeader } from "@/components/ui";
import { apiGetList } from "@/lib/api";
import type { OrderSummary } from "@/lib/types";

export default function DriverAssignmentsPage() {
  const [window, setWindow] = useState("active");
  const { data, isLoading, error } = useQuery({
    queryKey: ["driver-assignments", window],
    queryFn: () => apiGetList<OrderSummary>(`/driver/assignments?window=${window}`),
  });

  return (
    <div>
      <PageHeader eyebrow="Assigned orders" title="Work assigned to you" description="Open a stop to accept it, capture proof and progress the parcel." actions={<select className="input !w-auto" value={window} onChange={(event) => setWindow(event.target.value)}><option value="active">Active</option><option value="completed">Completed</option><option value="all">All</option></select>} />
      {isLoading ? <p className="text-sm text-muted">Loading assignments…</p> : null}
      {error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-red-ink">{(error as Error).message}</p> : null}
      {data ? <OrderList orders={data.data} hrefBase="/driver/assignments" emptyTitle="No assignments in this view" emptyDescription="A manager must dispatch work to you first." /> : null}
    </div>
  );
}
