"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Callout, Field } from "@/components/ui";
import { ApiError, apiPatch } from "@/lib/api";
import type { PartnerProfile } from "@/lib/types";

export default function PartnerProfileForm({ profile }: { profile: PartnerProfile }) {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function save(formData: FormData) {
    setBusy(true);
    setError(null);
    setMessage(null);
    const areas = String(formData.get("service_areas") ?? "")
      .split(",")
      .map((area) => area.trim())
      .filter(Boolean);
    try {
      await apiPatch("/partners/me", {
        company_name: String(formData.get("company_name") ?? ""),
        vehicle_type: String(formData.get("vehicle_type") ?? profile.vehicle_type),
        max_weight_kg: Number(formData.get("max_weight_kg")),
        max_volume_m3: Number(formData.get("max_volume_m3")),
        accepts_fragile: formData.get("accepts_fragile") === "on",
        accepts_restricted: formData.get("accepts_restricted") === "on",
        availability: String(formData.get("availability") ?? profile.availability),
        service_areas: areas,
        operating_start_hour: Number(formData.get("operating_start_hour")),
        operating_end_hour: Number(formData.get("operating_end_hour")),
        phone: String(formData.get("phone") ?? ""),
      });
      setMessage("Vehicle and availability settings saved.");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not save your partner profile.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form action={save} className="card card-pad space-y-5">
      <div>
        <h2 className="section-title">Vehicle, capacity and operating area</h2>
        <p className="mt-1 text-sm text-muted">
          Only verified and available partners are offered batches. Capacity is checked at every stop, not just at pickup.
        </p>
      </div>
      {message ? <Callout tone="accent">{message}</Callout> : null}
      {error ? <Callout tone="danger">{error}</Callout> : null}
      <div className="field-grid">
        <Field label="Business / courier name" htmlFor="partner-company">
          <input id="partner-company" name="company_name" className="input" defaultValue={profile.company_name} required />
        </Field>
        <Field label="Contact phone" htmlFor="partner-phone">
          <input id="partner-phone" name="phone" className="input" defaultValue={profile.phone ?? ""} />
        </Field>
        <Field label="Vehicle type" htmlFor="partner-vehicle">
          <select id="partner-vehicle" name="vehicle_type" className="input" defaultValue={profile.vehicle_type}>
            <option value="bike">Bike</option>
            <option value="car">Car</option>
            <option value="van">Van</option>
            <option value="truck">Truck</option>
          </select>
        </Field>
        <Field label="Availability" htmlFor="partner-availability">
          <select id="partner-availability" name="availability" className="input" defaultValue={profile.availability}>
            <option value="available">Available for new batches</option>
            <option value="on_route">On route</option>
            <option value="unavailable">Unavailable</option>
          </select>
        </Field>
        <Field label="Max weight (kg)" htmlFor="partner-weight">
          <input id="partner-weight" name="max_weight_kg" type="number" min="1" max="200" step="1" className="input" defaultValue={profile.max_weight_kg} />
        </Field>
        <Field label="Max volume (m³)" htmlFor="partner-volume">
          <input id="partner-volume" name="max_volume_m3" type="number" min="0.01" max="5" step="0.01" className="input" defaultValue={profile.max_volume_m3} />
        </Field>
        <Field label="Operating start hour" htmlFor="partner-start" hint="24-hour clock, local time.">
          <input id="partner-start" name="operating_start_hour" type="number" min="0" max="23" className="input" defaultValue={profile.operating_hours.start_hour} />
        </Field>
        <Field label="Operating end hour" htmlFor="partner-end">
          <input id="partner-end" name="operating_end_hour" type="number" min="1" max="24" className="input" defaultValue={profile.operating_hours.end_hour} />
        </Field>
        <Field label="Service areas" htmlFor="partner-areas" hint="Comma-separated area names. An empty list means no restriction." className="sm:col-span-2">
          <input id="partner-areas" name="service_areas" className="input" defaultValue={profile.service_areas.join(", ")} placeholder="Barasat, Salt Lake, New Town" />
        </Field>
      </div>
      <fieldset className="flex flex-wrap gap-5 rounded-control border bg-surface-muted px-4 py-3 text-sm">
        <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-muted">Handling capability</legend>
        <label className="flex items-center gap-2">
          <input type="checkbox" name="accepts_fragile" defaultChecked={profile.accepts_fragile} className="accent-[#087c60]" />
          Fragile parcels
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" name="accepts_restricted" defaultChecked={profile.accepts_restricted} className="accent-[#087c60]" />
          Restricted items (dedicated vehicle)
        </label>
      </fieldset>
      <button type="submit" className="btn btn-primary" disabled={busy}>
        {busy ? <Loader2 size={16} className="animate-spin" aria-hidden /> : null}
        Save vehicle settings
      </button>
    </form>
  );
}
