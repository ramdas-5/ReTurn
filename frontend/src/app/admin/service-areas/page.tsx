"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button, ErrorText } from "@/components/ui-bits";
import { Card, Field, PageHeader } from "@/components/ui";
import { ApiError, apiGet, apiGetList, apiPatch, apiPost } from "@/lib/api";
import type { ServiceArea } from "@/lib/types";

export default function AdminServiceAreasPage() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const areas = useQuery({ queryKey: ["admin-service-areas"], queryFn: () => apiGetList<ServiceArea>("/admin/service-areas") });

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("create");
    setError(null);
    setMessage(null);
    const form = new FormData(event.currentTarget);
    try {
      await apiPost("/admin/service-areas", {
        name: form.get("name"), city: form.get("city"), state: form.get("state"),
        radius_km: Number(form.get("radius_km")),
        center_latitude: Number(form.get("center_latitude")),
        center_longitude: Number(form.get("center_longitude")),
        postal_codes: form.get("postal_codes"),
        is_active: true,
      });
      setMessage("Service area created.");
      await queryClient.invalidateQueries({ queryKey: ["admin-service-areas"] });
      event.currentTarget.reset();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Service area could not be created.");
    } finally { setBusy(null); }
  }

  async function update(area: ServiceArea, event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(`area-${area.id}`);
    setError(null);
    setMessage(null);
    try {
      await apiPatch(`/admin/service-areas/${area.id}`, {
        radius_km: Number(form.get("radius_km")),
        is_active: form.get("is_active") === "on",
      });
      setMessage(`${area.name} updated.`);
      await queryClient.invalidateQueries({ queryKey: ["admin-service-areas"] });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Service area could not be updated.");
    } finally { setBusy(null); }
  }

  return (
    <div>
      <PageHeader eyebrow="Service areas" title="Where ReTurn operates" description="Orders are accepted only when both pickup and delivery points fall inside an active service area. Radius and centre are authoritative." />
      {error ? <ErrorText>{error}</ErrorText> : null}
      {message ? <p className="mb-4 rounded-control bg-accent-soft px-3 py-2 text-sm text-accent-strong">{message}</p> : null}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {areas.data?.data.map((area) => (
          <form key={area.id} onSubmit={(event) => update(area, event)} className="card card-pad space-y-2">
            <div className="flex items-start justify-between gap-2"><div><p className="font-semibold">{area.name}</p><p className="text-xs text-muted">{area.city}, {area.state}</p></div><span className={`chip ${area.is_active ? "chip-green" : "chip-neutral"}`}>{area.is_active ? "active" : "inactive"}</span></div>
            <p className="text-xs text-muted">{area.manager_count ?? 0} managers · {area.driver_count ?? 0} drivers</p>
            <p className="text-xs text-muted">Centre {area.center?.latitude ?? area.center_latitude}, {area.center?.longitude ?? area.center_longitude}</p>
            <div className="grid grid-cols-2 gap-2">
              <Field label="Radius (km)"><input name="radius_km" type="number" step="0.5" min={0.5} className="input" defaultValue={area.radius_km} /></Field>
              <label className="flex items-end gap-2 pb-2 text-sm"><input type="checkbox" name="is_active" defaultChecked={area.is_active} /> Active</label>
            </div>
            <Button type="submit" busy={busy === `area-${area.id}`} className="btn btn-secondary btn-sm">Save area</Button>
          </form>
        ))}
      </div>
      <form onSubmit={create} className="card card-pad mt-8 space-y-4">
        <h2 className="section-title">Add a service area</h2>
        <div className="field-grid">
          <Field label="Name"><input name="name" className="input" required /></Field>
          <Field label="City"><input name="city" className="input" defaultValue="Kolkata" required /></Field>
          <Field label="State"><input name="state" className="input" defaultValue="West Bengal" /></Field>
          <Field label="Radius (km)"><input name="radius_km" type="number" step="0.5" className="input" defaultValue={8} required /></Field>
          <Field label="Centre latitude"><input name="center_latitude" type="number" step="0.000001" className="input" required /></Field>
          <Field label="Centre longitude"><input name="center_longitude" type="number" step="0.000001" className="input" required /></Field>
          <Field label="Postal codes" className="sm:col-span-2"><input name="postal_codes" className="input" placeholder="Comma-separated" /></Field>
        </div>
        <Button type="submit" busy={busy === "create"}>Create service area</Button>
      </form>
    </div>
  );
}
