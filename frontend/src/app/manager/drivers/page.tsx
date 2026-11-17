"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Button, ErrorText } from "@/components/ui-bits";
import { Card, EmptyState, Field, PageHeader } from "@/components/ui";
import { ApiError, apiGet, apiGetList, apiPost } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { ServiceArea, Vehicle } from "@/lib/types";

type DriverRow = {
  driver: { id: number; full_name: string; email: string; phone: string | null; status: string };
  profile: { verification_status: string; completed_deliveries: number; vehicles: Vehicle[] } | null;
  duty: { status_label: string; last_heartbeat_at: string } | null;
  duty_label: string;
  is_live: boolean;
  last_location: { received_at: string; status_label: string } | null;
  active_batch: { id: number; batch_number: string } | null;
};

type CapacityProfile = { id: number; name: string; vehicle_type: string; max_weight_kg: number };

export default function ManagerDriversPage() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const drivers = useQuery({ queryKey: ["manager-drivers"], queryFn: () => apiGetList<DriverRow>("/manager/drivers") });
  const areas = useQuery({ queryKey: ["service-areas"], queryFn: () => apiGet<ServiceArea[]>("/service-areas") });
  const capacities = useQuery({ queryKey: ["capacity-profiles"], queryFn: () => apiGet<CapacityProfile[]>("/vehicle-capacity-profiles") });

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    const form = new FormData(event.currentTarget);
    try {
      const result = await apiPost<{ user: { email: string }; activation_token?: string }>("/users/drivers", {
        full_name: form.get("full_name"),
        email: form.get("email"),
        phone: form.get("phone"),
        license_number: form.get("license_number"),
        license_expiry: form.get("license_expiry"),
        verification_status: form.get("verification_status"),
        service_area_ids: form.getAll("service_area_ids").map(Number),
        vehicle: {
          capacity_profile_id: Number(form.get("capacity_profile_id")),
          registration_number: form.get("registration_number"),
          make: form.get("make"),
          model: form.get("model"),
          color: form.get("color"),
          year: form.get("year") ? Number(form.get("year")) : undefined,
        },
      });
      setMessage(`Driver ${result.user.email} created. Activation token: ${result.activation_token ?? "delivered separately"}`);
      await queryClient.invalidateQueries({ queryKey: ["manager-drivers"] });
      event.currentTarget.reset();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Driver could not be created.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader eyebrow="Driver management" title="Verified drivers in your areas" description="Drivers are provisioned by ReTurn staff; they cannot self-register." actions={<Link href="/manager/live" className="btn btn-secondary">Live tracking</Link>} />
      {error ? <ErrorText>{error}</ErrorText> : null}
      {message ? <p className="mb-4 rounded-control bg-accent-soft px-3 py-2 text-sm text-accent-strong">{message}</p> : null}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {drivers.data?.data.map((row) => (
          <Card key={row.driver.id}>
            <div className="flex items-start justify-between gap-2">
              <div><p className="font-semibold">{row.driver.full_name}</p><p className="text-xs text-muted">{row.driver.email}</p></div>
              <span className={`chip ${row.is_live ? "chip-green" : "chip-neutral"}`}>{row.duty_label}</span>
            </div>
            <p className="mt-2 text-sm text-muted">{row.profile?.verification_status.replaceAll("_", " ") ?? "No profile"} · {row.profile?.completed_deliveries ?? 0} deliveries</p>
            <p className="mt-1 text-xs text-muted">{row.active_batch ? `Batch ${row.active_batch.batch_number}` : "No active batch"}</p>
            <p className="mt-1 text-xs text-muted">{row.last_location ? `${row.last_location.status_label} · ${formatDateTime(row.last_location.received_at)}` : "Tracking unavailable"}</p>
          </Card>
        ))}
      </div>
      {drivers.data && drivers.data.data.length === 0 ? <EmptyState title="No drivers in scope" description="Ask an administrator to assign drivers to your service areas." /> : null}

      <form onSubmit={create} className="card card-pad mt-8 space-y-4">
        <h2 className="section-title">Create a driver</h2>
        <div className="field-grid">
          <Field label="Full name"><input name="full_name" className="input" required /></Field>
          <Field label="Email"><input name="email" type="email" className="input" required /></Field>
          <Field label="Phone"><input name="phone" className="input" required /></Field>
          <Field label="Licence number"><input name="license_number" className="input" /></Field>
          <Field label="Licence expiry"><input name="license_expiry" type="date" className="input" /></Field>
          <Field label="Verification"><select name="verification_status" className="input" defaultValue="verified"><option value="pending">Pending</option><option value="verified">Verified</option></select></Field>
          <Field label="Vehicle capacity"><select name="capacity_profile_id" className="input" required defaultValue=""><option value="" disabled>Choose capacity</option>{capacities.data?.map((row) => <option key={row.id} value={row.id}>{row.name} ({row.max_weight_kg} kg)</option>)}</select></Field>
          <Field label="Registration number"><input name="registration_number" className="input" required /></Field>
          <Field label="Make"><input name="make" className="input" /></Field>
          <Field label="Model"><input name="model" className="input" /></Field>
          <Field label="Colour"><input name="color" className="input" /></Field>
          <Field label="Year"><input name="year" type="number" className="input" /></Field>
        </div>
        <fieldset>
          <legend className="label">Service areas</legend>
          <div className="grid gap-2 sm:grid-cols-3">
            {areas.data?.map((area) => <label key={area.id} className="flex items-center gap-2 text-sm"><input type="checkbox" name="service_area_ids" value={area.id} /> {area.name}</label>)}
          </div>
        </fieldset>
        <Button type="submit" busy={busy}>Create driver account</Button>
      </form>
    </div>
  );
}
