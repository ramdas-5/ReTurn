"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button, ErrorText } from "@/components/ui-bits";
import { PageHeader } from "@/components/ui";
import { ApiError, apiGetList, apiPost } from "@/lib/api";
import type { OrderSummary } from "@/lib/types";

export default function DriverIssuesPage() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { data } = useQuery({
    queryKey: ["driver-issues-orders"],
    queryFn: () => apiGetList<OrderSummary>("/driver/assignments?window=active"),
  });

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    const form = new FormData(event.currentTarget);
    const orderId = form.get("order_id");
    try {
      await apiPost(`/driver/orders/${orderId}/exception`, {
        exception_type: form.get("exception_type"),
        description: form.get("description"),
      });
      setMessage("Issue reported. A manager will review it.");
      await queryClient.invalidateQueries({ queryKey: ["driver-issues-orders"] });
      event.currentTarget.reset();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Issue could not be reported.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader eyebrow="Report delivery issue" title="Something blocking this stop?" description="Exceptions are sent to the responsible manager. Reporting one never marks a delivery complete." />
      <form onSubmit={submit} className="card card-pad space-y-3">
        {error ? <ErrorText>{error}</ErrorText> : null}
        {message ? <p className="rounded-control bg-accent-soft px-3 py-2 text-sm text-accent-strong">{message}</p> : null}
        <div>
          <label className="label" htmlFor="order_id">Assigned order</label>
          <select id="order_id" name="order_id" className="input" required>
            <option value="">Choose an order</option>
            {data?.data.map((order) => <option key={order.id} value={order.id}>{order.order_number} · {order.pickup.area} → {order.delivery.area}</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="exception_type">Issue type</label>
          <select id="exception_type" name="exception_type" className="input" defaultValue="recipient_unavailable">
            <option value="recipient_unavailable">Recipient unavailable</option>
            <option value="address_not_found">Address not found</option>
            <option value="parcel_damaged">Parcel damaged</option>
            <option value="access_issue">Access issue</option>
            <option value="proof_capture_failed">Proof capture failed</option>
            <option value="vehicle_problem">Vehicle problem</option>
            <option value="other">Other</option>
          </select>
        </div>
        <div>
          <label className="label" htmlFor="description">Description</label>
          <textarea id="description" name="description" className="input" rows={4} required minLength={10} />
        </div>
        <Button type="submit" busy={busy}>Report issue</Button>
      </form>
    </div>
  );
}
