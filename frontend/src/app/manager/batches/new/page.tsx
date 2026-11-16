"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, ErrorText } from "@/components/ui-bits";
import { Card, Field, PageHeader } from "@/components/ui";
import { ApiError, apiGetList, apiPost } from "@/lib/api";
import { formatWindow } from "@/lib/format";
import type { BatchDetail, OrderSummary } from "@/lib/types";

type DriverRow = {
  driver: { id: number; full_name: string };
  duty_label: string;
  is_live: boolean;
  profile: { vehicles: Array<{ id: number; registration_number: string; capacity?: { max_weight_kg: number } }> } | null;
};

export default function NewBatchPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { data: orders } = useQuery({
    queryKey: ["manager-orders", "batch-candidates"],
    queryFn: () => apiGetList<OrderSummary>("/manager/orders?status=awaiting_assignment&per_page=100"),
  });
  const { data: drivers } = useQuery({
    queryKey: ["manager-drivers"],
    queryFn: () => apiGetList<DriverRow>("/manager/drivers"),
  });

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const form = new FormData(event.currentTarget);
    try {
      const batch = await apiPost<BatchDetail>("/manager/batches", {
        order_ids: form.getAll("order_ids").map(Number),
        driver_id: Number(form.get("driver_id")),
        planned_start: form.get("planned_start") ? new Date(String(form.get("planned_start"))).toISOString() : undefined,
        notes: form.get("notes") || undefined,
      });
      router.push(`/manager/batches/${batch.id}`);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Batch could not be created.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader eyebrow="Batch creation" title="Build a compatible shared route" description="Select approved orders and a driver whose vehicle can carry every parcel without breaking windows, areas or handling rules." back={{ href: "/manager/batches", label: "Batches" }} />
      <form onSubmit={submit} className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <Card>
          <h2 className="section-title">Approved orders</h2>
          {error ? <div className="mt-3"><ErrorText>{error}</ErrorText></div> : null}
          <div className="mt-3 space-y-2">
            {orders?.data.map((order) => (
              <label key={order.id} className="flex cursor-pointer items-start gap-3 rounded-control border p-3 text-sm hover:bg-surface-muted">
                <input type="checkbox" name="order_ids" value={order.id} className="mt-1" />
                <span>
                  <span className="font-semibold">{order.order_number}</span> · {order.service_type} · {order.pickup.area} → {order.delivery.area}
                  <span className="block text-xs text-muted">{formatWindow(order.pickup.window_start, order.pickup.window_end)} · {order.parcel.weight_kg} kg</span>
                </span>
              </label>
            ))}
            {orders && orders.data.length === 0 ? <p className="text-sm text-muted">No approved orders are waiting for assignment.</p> : null}
          </div>
        </Card>
        <div className="space-y-4">
          <Card>
            <h2 className="section-title">Driver</h2>
            <div className="mt-3 space-y-3">
              <Field label="Driver">
                <select name="driver_id" className="input" required defaultValue="">
                  <option value="" disabled>Choose a driver</option>
                  {drivers?.data.map((row) => <option key={row.driver.id} value={row.driver.id}>{row.driver.full_name} · {row.duty_label}{row.is_live ? " · live" : ""}</option>)}
                </select>
              </Field>
              <Field label="Planned start"><input name="planned_start" type="datetime-local" className="input" /></Field>
              <Field label="Notes"><textarea name="notes" className="input" rows={3} /></Field>
              <Button type="submit" busy={busy}>Create batch</Button>
            </div>
          </Card>
          <p className="text-xs leading-5 text-muted">If the server finds an incompatible parcel, batch creation is refused with the specific capacity or window blocker. No route is fabricated.</p>
        </div>
      </form>
    </div>
  );
}
