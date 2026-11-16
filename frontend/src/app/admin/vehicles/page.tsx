"use client";

import { useQuery } from "@tanstack/react-query";

import { VehicleVerificationActions } from "@/components/AdminAccountActions";
import { PageHeader } from "@/components/ui";
import { apiGetList } from "@/lib/api";
import type { Vehicle } from "@/lib/types";

type Row = Vehicle & { driver: { id: number; full_name: string; email: string; verification_status: string } | null };

export default function AdminVehiclesPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["admin-vehicles"], queryFn: () => apiGetList<Row>("/admin/vehicles?per_page=100") });

  return (
    <div>
      <PageHeader eyebrow="Fleet management" title="Vehicles and capacity" description="Capacity limits come from the configured vehicle profile. Verification controls whether dispatch may assign the vehicle." />
      {isLoading ? <p className="text-sm text-muted">Loading fleet…</p> : null}
      {error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-[#8c2f2f]">{(error as Error).message}</p> : null}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data?.data.map((row) => (
          <article key={row.id} className="card card-pad">
            <div className="flex items-start justify-between gap-2">
              <div><p className="font-semibold">{row.registration_number}</p><p className="text-xs capitalize text-muted">{row.vehicle_type} · {row.make ?? ""} {row.model ?? ""}</p></div>
              <span className={`chip ${row.verification_status === "verified" ? "chip-green" : row.verification_status === "rejected" ? "chip-red" : "chip-amber"}`}>{row.verification_status}</span>
            </div>
            <p className="mt-2 text-xs text-muted">{row.driver?.full_name ?? "No driver"} · {row.driver?.email ?? ""}</p>
            <p className="mt-1 text-xs text-muted">{row.capacity ? `${row.capacity.max_weight_kg} kg · ${row.capacity.max_volume_m3} m³ · ${row.capacity.max_parcels} parcels` : "No capacity profile"}</p>
            <p className="mt-1 text-xs text-muted">{row.is_active ? "Active" : "Inactive"}</p>
            {row.verification_status !== "verified" ? <VehicleVerificationActions vehicleId={row.id} /> : null}
          </article>
        ))}
      </div>
      {data && data.data.length === 0 ? <p className="text-sm text-muted">No vehicles on file.</p> : null}
    </div>
  );
}
