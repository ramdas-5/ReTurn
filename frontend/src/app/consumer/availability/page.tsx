"use client";

import { useState } from "react";

import { Button } from "@/components/ui-bits";
import { Card, Field, PageHeader } from "@/components/ui";
import { ApiError, apiGet } from "@/lib/api";

type Availability = {
  serviceable: boolean;
  available: boolean;
  availability_label: string;
  drivers_on_duty: number;
  drivers_scheduled: number;
  reasons: string[];
  pickup_area: { name: string } | null;
  delivery_area: { name: string } | null;
  checked_at: string;
  disclaimer: string;
};

export default function AvailabilityPage() {
  const [result, setResult] = useState<Availability | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const form = new FormData(event.currentTarget);
    const params = new URLSearchParams();
    form.forEach((value, key) => params.set(key, String(value)));
    if (form.get("window_start")) params.set("window_start", new Date(String(form.get("window_start"))).toISOString());
    if (form.get("window_end")) params.set("window_end", new Date(String(form.get("window_end"))).toISOString());
    try {
      setResult(await apiGet<Availability>(`/availability?${params.toString()}`));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Availability check failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader eyebrow="Service availability" title="Is a pickup realistic?" description="This answer comes from active service areas, verified driver schedules and live duty sessions — not invented availability." />
      <form onSubmit={submit} className="card card-pad space-y-4">
        <div className="field-grid">
          <Field label="Pickup area"><input name="pickup_area" className="input" required placeholder="e.g. Barasat" /></Field>
          <Field label="Delivery area"><input name="delivery_area" className="input" required placeholder="e.g. Salt Lake" /></Field>
          <Field label="Pickup latitude"><input name="pickup_latitude" type="number" step="0.000001" className="input" defaultValue="22.724" required /></Field>
          <Field label="Pickup longitude"><input name="pickup_longitude" type="number" step="0.000001" className="input" defaultValue="88.478" required /></Field>
          <Field label="Delivery latitude"><input name="delivery_latitude" type="number" step="0.000001" className="input" defaultValue="22.58" required /></Field>
          <Field label="Delivery longitude"><input name="delivery_longitude" type="number" step="0.000001" className="input" defaultValue="88.41" required /></Field>
          <Field label="Pickup window start"><input name="window_start" type="datetime-local" className="input" required /></Field>
          <Field label="Pickup window end"><input name="window_end" type="datetime-local" className="input" required /></Field>
        </div>
        <Button busy={busy} type="submit">Check availability</Button>
      </form>
      {error ? <p className="mt-4 rounded-control bg-red-soft px-4 py-3 text-sm text-red-ink">{error}</p> : null}
      {result ? (
        <Card className="mt-4">
          <p className={`chip ${result.serviceable ? "chip-teal" : "chip-red"}`}>{result.availability_label}</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 text-sm">
            <p>Pickup area: {result.pickup_area?.name ?? "Outside service area"}</p>
            <p>Delivery area: {result.delivery_area?.name ?? "Outside service area"}</p>
            <p>Drivers on duty: {result.drivers_on_duty}</p>
            <p>Drivers scheduled: {result.drivers_scheduled}</p>
          </div>
          {result.reasons.length ? <p className="mt-3 text-sm text-amber-ink">Reasons: {result.reasons.join(", ")}</p> : null}
          <p className="mt-4 text-xs leading-5 text-muted">{result.disclaimer}</p>
        </Card>
      ) : null}
    </div>
  );
}
