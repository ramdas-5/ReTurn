"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { PageHeader, StatCard } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

type Operations = {
  drivers: Array<{
    driver: { id: number; full_name: string; phone: string | null };
    duty: { status: string; label: string; last_heartbeat_at: string };
    location: { latitude: number; longitude: number; received_at: string; is_recent: boolean; status_label: string } | null;
    tracking_status: string;
    active_batch: { id: number; batch_number: string; status: string } | null;
  }>;
  counts: { drivers_on_duty: number; pending_pickups: number; in_transit: number; active_batches: number; open_exceptions: number };
  generated_at: string;
  note: string;
};

export default function AdminOperationsPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["admin-operations"], queryFn: () => apiGet<Operations>("/admin/operations/live"), refetchInterval: 60_000 });

  return (
    <div>
      <PageHeader eyebrow="Global live operations" title="Duty, tracking and active work" description="Only reported locations are shown, labelled live recent, stale or unavailable. Nothing is interpolated." actions={<Link href="/admin/routes" className="btn btn-secondary">Route monitor</Link>} />
      {isLoading ? <p className="text-sm text-muted">Loading operations…</p> : null}
      {error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-red-ink">{(error as Error).message}</p> : null}
      {data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <StatCard label="On duty" value={data.counts.drivers_on_duty} />
            <StatCard label="Pending pickups" value={data.counts.pending_pickups} />
            <StatCard label="In transit" value={data.counts.in_transit} />
            <StatCard label="Active batches" value={data.counts.active_batches} />
            <StatCard label="Open exceptions" value={data.counts.open_exceptions} tone="red" />
          </div>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {data.drivers.map((row) => (
              <article key={row.driver.id} className="card card-pad">
                <p className="font-semibold">{row.driver.full_name}</p>
                <p className="text-xs text-muted">{row.driver.phone ?? "No phone"} · {row.duty.label}</p>
                <p className="mt-2 text-xs">
                  <span className={`chip ${row.tracking_status === "live_recent" ? "chip-green" : row.tracking_status === "stale" ? "chip-amber" : "chip-neutral"}`}>{row.tracking_status.replaceAll("_", " ")}</span>
                </p>
                <p className="mt-2 text-xs text-muted">{row.location ? `${row.location.status_label} · ${formatDateTime(row.location.received_at)}` : "No location reported"}</p>
                <p className="mt-2 text-xs">{row.active_batch ? <Link className="link" href={`/admin/batches/${row.active_batch.id}`}>{row.active_batch.batch_number}</Link> : "No active batch"}</p>
              </article>
            ))}
          </div>
          <p className="mt-4 text-xs leading-5 text-muted">{data.note} Generated {formatDateTime(data.generated_at)}.</p>
        </>
      ) : null}
    </div>
  );
}
