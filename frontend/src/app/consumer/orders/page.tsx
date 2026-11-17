"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import OrderList from "@/components/OrderList";
import { PageHeader } from "@/components/ui";
import { apiGetList } from "@/lib/api";
import type { OrderSummary } from "@/lib/types";

export default function ConsumerOrdersPage() {
  const [window, setWindow] = useState("active");
  const [service, setService] = useState("");
  const { data, isLoading, error } = useQuery({
    queryKey: ["consumer-orders", window, service],
    queryFn: () => {
      const params = new URLSearchParams();
      if (window) params.set("window", window);
      if (service) params.set("service_type", service);
      return apiGetList<OrderSummary>(`/orders?${params.toString()}`);
    },
  });

  return (
    <div>
      <PageHeader
        eyebrow="My orders"
        title="Every request you have made"
        description="Track parcels, returns and their complete status history."
        actions={<><a href="/consumer/parcels/new" className="btn btn-primary">Send parcel</a><a href="/consumer/returns/new" className="btn btn-secondary">Return product</a></>}
      />
      <div className="mb-4 flex flex-wrap gap-2">
        {["active", "completed", "cancelled", ""].map((value) => (
          <button key={value || "all"} className={`chip ${window === value ? "chip-teal" : "chip-neutral"}`} onClick={() => setWindow(value)}>
            {value || "All"}
          </button>
        ))}
        <select className="input !w-auto !py-1.5 text-sm" value={service} onChange={(event) => setService(event.target.value)}>
          <option value="">All services</option>
          <option value="parcel">Parcels</option>
          <option value="return">Returns</option>
        </select>
      </div>
      {isLoading ? <p className="text-sm text-muted">Loading orders…</p> : null}
      {error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-red-ink">{(error as Error).message}</p> : null}
      {data ? <OrderList orders={data.data} hrefBase="/consumer/orders" emptyTitle="No orders in this view" emptyDescription="Try another filter or create a new request." /> : null}
    </div>
  );
}
