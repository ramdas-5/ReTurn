"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { AccountStatusActions, DriverVerificationActions } from "@/components/AdminAccountActions";
import { PageHeader } from "@/components/ui";
import { apiGetList } from "@/lib/api";
import type { ApiUser, Vehicle } from "@/lib/types";

type Row = {
  user: ApiUser;
  verification_status: string;
  duty_status: string;
  completed_deliveries: number;
  service_areas: Array<{ name: string }>;
  vehicles: Vehicle[];
  active_assignments: number;
  active_batches: number;
};

export default function AdminDriversPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["admin-drivers"], queryFn: () => apiGetList<Row>("/admin/drivers") });

  return (
    <div>
      <PageHeader eyebrow="Driver management" title="Drivers and verification" description="Driver accounts are never self-registered. Verification changes are audited." actions={<Link href="/admin/accounts/new" className="btn btn-primary">Create driver</Link>} />
      {isLoading ? <p className="text-sm text-muted">Loading drivers…</p> : null}
      {error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-[#8c2f2f]">{(error as Error).message}</p> : null}
      <div className="grid gap-4 sm:grid-cols-2">
        {data?.data.map((row) => (
          <article key={row.user.id} className="card card-pad">
            <div className="flex items-start justify-between gap-2">
              <div><p className="font-semibold">{row.user.full_name}</p><p className="text-xs text-muted">{row.user.email} · {row.user.phone}</p></div>
              <span className={`chip ${row.verification_status === "verified" ? "chip-green" : row.verification_status === "rejected" ? "chip-red" : "chip-amber"}`}>{row.verification_status.replaceAll("_", " ")}</span>
            </div>
            <p className="mt-2 text-[13px] text-muted">Duty {row.duty_status} · {row.completed_deliveries} completed · {row.active_assignments} active assignments</p>
            <p className="mt-1 text-xs text-muted">{row.vehicles.map((vehicle) => `${vehicle.vehicle_type} ${vehicle.registration_number}`).join(", ") || "No vehicles"}</p>
            <p className="mt-1 text-xs text-muted">{row.service_areas?.map((area) => area.name).join(", ") || "No service areas"}</p>
            {row.verification_status !== "verified" ? <DriverVerificationActions userId={row.user.id} /> : null}
            <div className="mt-2"><AccountStatusActions userId={row.user.id} status={row.user.status} /></div>
          </article>
        ))}
      </div>
      {data && data.data.length === 0 ? <p className="text-sm text-muted">No drivers.</p> : null}
    </div>
  );
}
