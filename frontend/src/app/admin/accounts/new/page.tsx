"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Button, ErrorText } from "@/components/ui-bits";
import { Card, Field, PageHeader } from "@/components/ui";
import { ApiError, apiGet, apiPost } from "@/lib/api";
import type { ServiceArea } from "@/lib/types";

type Capacity = { id: number; name: string; max_weight_kg: number };

export default function NewAccountPage() {
  const [mode, setMode] = useState<"manager" | "driver">("manager");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const areas = useQuery({ queryKey: ["service-areas"], queryFn: () => apiGet<ServiceArea[]>("/service-areas") });
  const capacities = useQuery({ queryKey: ["capacity-profiles"], queryFn: () => apiGet<Capacity[]>("/vehicle-capacity-profiles") });

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    const form = new FormData(event.currentTarget);
    const common = {
      full_name: form.get("full_name"), email: form.get("email"), phone: form.get("phone"),
      service_area_ids: form.getAll("service_area_ids").map(Number),
    };
    try {
      const result = await apiPost<{ user: { email: string }; activation_token?: string }>(
        mode === "manager" ? "/users/managers" : "/users/drivers",
        mode === "manager"
          ? { ...common, employee_code: form.get("employee_code"), notes: form.get("notes") }
          : {
              ...common,
              license_number: form.get("license_number"),
              license_expiry: form.get("license_expiry"),
              verification_status: form.get("verification_status"),
              vehicle: {
                capacity_profile_id: Number(form.get("capacity_profile_id")),
                registration_number: form.get("registration_number"),
                make: form.get("make"), model: form.get("model"), color: form.get("color"),
                year: form.get("year") ? Number(form.get("year")) : undefined,
              },
            },
      );
      setMessage(`${mode} created: ${result.user.email}. Activation token: ${result.activation_token ?? "sent separately"}`);
      event.currentTarget.reset();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Account could not be created.");
    } finally { setBusy(false); }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader eyebrow="Create account" title="Provision staff or a driver" description="Only administrators can create managers. Both administrators and managers can create drivers; passwords are set through a one-time activation token." />
      <div className="mb-4 flex gap-2">
        <button className={`chip ${mode === "manager" ? "chip-teal" : "chip-neutral"}`} onClick={() => setMode("manager")}>Manager</button>
        <button className={`chip ${mode === "driver" ? "chip-teal" : "chip-neutral"}`} onClick={() => setMode("driver")}>Driver</button>
      </div>
      <form onSubmit={submit} className="card card-pad space-y-4">
        {error ? <ErrorText>{error}</ErrorText> : null}
        {message ? <p className="rounded-control bg-accent-soft px-3 py-2 text-sm text-accent-strong">{message}</p> : null}
        <div className="field-grid">
          <Field label="Full name"><input name="full_name" className="input" required /></Field>
          <Field label="Email"><input name="email" type="email" className="input" required /></Field>
          <Field label="Phone"><input name="phone" className="input" required /></Field>
          {mode === "manager" ? <Field label="Employee code"><input name="employee_code" className="input" /></Field> : (
            <>
              <Field label="Licence number"><input name="license_number" className="input" /></Field>
              <Field label="Licence expiry"><input name="license_expiry" type="date" className="input" /></Field>
              <Field label="Verification"><select name="verification_status" className="input" defaultValue="pending"><option value="pending">Pending</option><option value="verified">Verified</option></select></Field>
              <Field label="Capacity profile"><select name="capacity_profile_id" className="input" required defaultValue=""><option value="" disabled>Choose capacity</option>{capacities.data?.map((row) => <option key={row.id} value={row.id}>{row.name} ({row.max_weight_kg} kg)</option>)}</select></Field>
              <Field label="Registration"><input name="registration_number" className="input" required /></Field>
              <Field label="Make"><input name="make" className="input" /></Field>
              <Field label="Model"><input name="model" className="input" /></Field>
              <Field label="Colour"><input name="color" className="input" /></Field>
              <Field label="Year"><input name="year" type="number" className="input" /></Field>
            </>
          )}
        </div>
        <fieldset>
          <legend className="label">Service areas</legend>
          <div className="grid gap-2 sm:grid-cols-3">{areas.data?.map((area) => <label key={area.id} className="flex items-center gap-2 text-sm"><input type="checkbox" name="service_area_ids" value={area.id} /> {area.name}</label>)}</div>
        </fieldset>
        {mode === "manager" ? <Field label="Notes"><textarea name="notes" className="input" rows={2} /></Field> : null}
        <Button type="submit" busy={busy}>Create {mode} account</Button>
      </form>
    </div>
  );
}
