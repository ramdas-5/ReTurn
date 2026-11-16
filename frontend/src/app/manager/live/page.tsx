"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { PageHeader } from "@/components/ui";
import { apiGetList } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

type LiveRow = {
  driver: { id: number; full_name: string; phone: string | null };
  duty_label: string;
  tracking_label: string;
  location: { latitude: number; longitude: number; received_at: string; status_label: string; is_recent: boolean } | null;
  active_batch: { id: number; batch_number: string; status: string } | null;
  next_stop: { kind: string; address?: { area?: string } } | null;
};

export default function ManagerLivePage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["manager-live"],
    queryFn: () => apiGetList<LiveRow>("/manager/drivers/live"),
  });

  return (
    <div>
      <PageHeader eyebrow="Live operations" title="Drivers on duty" description="Only the latest reported on-duty location is shown. “Tracking unavailable” and stale readings are labelled honestly — ReTurn does not invent GPS." />
      {isLoading ? <p className="text-sm text-muted">Loading live drivers…</p> : null}
      {error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-[#8c2f2f]">{(error as Error).message}</p> : null}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data?.data.map((row) => (
          <article key={row.driver.id} className="card card-pad">
            <div className="flex items-start justify-between gap-2">
              <div><p className="font-semibold">{row.driver.full_name}</p><p className="text-xs text-muted">{row.driver.phone ?? "No phone"}</p></div>
              <span className={`chip ${row.location?.is_recent ? "chip-green" : row.location ? "chip-amber" : "chip-neutral"}`}>{row.tracking_label}</span>
            </div>
            <p className="mt-2 text-sm">{row.duty_label}</p>
            <p className="mt-1 text-xs text-muted">{row.location ? `${row.location.status_label} · ${formatDateTime(row.location.received_at)}` : "No location reported"}</p>
            {row.location ? <a className="link mt-1 inline-block text-xs" href={`https://www.openstreetmap.org/?mlat=${row.location.latitude}&mlon=${row.location.longitude}#map=15/${row.location.latitude}/${row.location.longitude}`} target="_blank" rel="noreferrer">Open reported point</a> : null}
            <div className="mt-3 border-t pt-2 text-xs">
              {row.active_batch ? <Link href={`/manager/batches/${row.active_batch.id}`} className="link">{row.active_batch.batch_number} · {row.active_batch.status}</Link> : "No active batch"}
              {row.next_stop ? <p className="mt-1 text-muted">Next: {row.next_stop.kind} {row.next_stop.address?.area ?? ""}</p> : null}
            </div>
          </article>
        ))}
      </div>
      {data && data.data.length === 0 ? <p className="text-sm text-muted">No drivers currently have an open duty session.</p> : null}
    </div>
  );
}
