"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button, ErrorText } from "@/components/ui-bits";
import { Card, Field, PageHeader } from "@/components/ui";
import { ApiError, apiGet, apiPatch } from "@/lib/api";
import type { DriverProfile, Vehicle } from "@/lib/types";

type ProfilePayload = {
  user: { id: number; full_name: string; email: string; phone: string | null };
  driver_profile: DriverProfile;
  service_areas: Array<{ id: number; name: string; city: string }>;
};

export default function DriverVehiclePage() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { data } = useQuery({
    queryKey: ["driver-profile"],
    queryFn: () => apiGet<ProfilePayload>("/driver/profile"),
  });

  const vehicles: Vehicle[] = data?.driver_profile.vehicles ?? [];

  async function save(event: React.FormEvent<HTMLFormElement>, vehicle: Vehicle) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    const form = new FormData(event.currentTarget);
    try {
      await apiPatch("/driver/vehicle", {
        vehicle_id: vehicle.id,
        make: form.get("make"),
        model: form.get("model"),
        color: form.get("color"),
        year: form.get("year") ? Number(form.get("year")) : undefined,
      });
      await queryClient.invalidateQueries({ queryKey: ["driver-profile"] });
      setMessage("Vehicle updated.");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Vehicle could not be updated.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader eyebrow="Vehicle profile" title="Your delivery vehicle" description="Managers assign work against this vehicle's real capacity. Verification is controlled by ReTurn staff." />
      {error ? <div className="mb-4"><ErrorText>{error}</ErrorText></div> : null}
      {message ? <p className="mb-4 rounded-control bg-accent-soft px-3 py-2 text-sm text-accent-strong">{message}</p> : null}
      <div className="grid gap-5 lg:grid-cols-2">
        {vehicles.map((vehicle) => (
          <form key={vehicle.id} onSubmit={(event) => save(event, vehicle)} className="card card-pad space-y-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <h2 className="section-title">{vehicle.registration_number}</h2>
                <p className="text-sm capitalize text-muted">{vehicle.vehicle_type} · {vehicle.capacity?.name}</p>
              </div>
              <span className={`chip ${vehicle.verification_status === "verified" ? "chip-green" : "chip-amber"}`}>{vehicle.verification_status.replaceAll("_", " ")}</span>
            </div>
            {vehicle.capacity ? (
              <p className="rounded-control bg-surface-muted p-3 text-xs leading-5 text-muted">
                Max {vehicle.capacity.max_weight_kg} kg · {vehicle.capacity.max_volume_m3} m³ · {vehicle.capacity.max_parcels} parcels ·
                {" "}{vehicle.capacity.supports_fragile ? "fragile allowed" : "no fragile"} · {vehicle.is_active ? "active" : "inactive"}
              </p>
            ) : null}
            <div className="grid grid-cols-2 gap-3">
              <Field label="Make"><input name="make" className="input" defaultValue={vehicle.make ?? ""} /></Field>
              <Field label="Model"><input name="model" className="input" defaultValue={vehicle.model ?? ""} /></Field>
              <Field label="Colour"><input name="color" className="input" defaultValue={vehicle.color ?? ""} /></Field>
              <Field label="Year"><input name="year" type="number" className="input" defaultValue={vehicle.year ?? ""} /></Field>
            </div>
            <Button type="submit" busy={busy}>Save vehicle details</Button>
          </form>
        ))}
        {data && vehicles.length === 0 ? <Card><p className="text-sm text-muted">No vehicle on file. Ask an administrator to add one before dispatch can assign work.</p></Card> : null}
      </div>
    </div>
  );
}
