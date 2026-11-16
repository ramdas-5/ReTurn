"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { EmptyState, PageHeader } from "@/components/ui";
import { StatusBadge } from "@/components/Status";
import { apiGetList } from "@/lib/api";
import { formatDateTime, formatKm } from "@/lib/format";
import type { BatchSummary } from "@/lib/types";

export default function ManagerBatchesPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["manager-batches"],
    queryFn: () => apiGetList<BatchSummary>("/manager/batches?per_page=100"),
  });

  return (
    <div>
      <PageHeader eyebrow="Batches & route management" title="Shared routes" description="A batch is built only when capacity, windows, handling and service areas are compatible." actions={<Link href="/manager/batches/new" className="btn btn-primary">Create batch</Link>} />
      {isLoading ? <p className="text-sm text-muted">Loading batches…</p> : null}
      {error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-[#8c2f2f]">{(error as Error).message}</p> : null}
      <div className="grid gap-4 sm:grid-cols-2">
        {data?.data.map((batch) => (
          <Link key={batch.id} href={`/manager/batches/${batch.id}`} className="card card-pad hover:border-accent/50">
            <div className="flex items-start justify-between gap-2">
              <div><p className="font-bold">{batch.batch_number}</p><p className="text-sm text-muted">{batch.driver?.full_name ?? "No driver"} · {batch.order_count} orders</p></div>
              <StatusBadge status={batch.status} />
            </div>
            <p className="mt-3 text-[13px] text-muted">{formatDateTime(batch.planned_start)} · {formatKm(batch.distance_km)} · {batch.completed_stops}/{batch.total_stops} stops</p>
            <p className="mt-1 text-xs text-muted">Distance basis: {batch.distance_source}</p>
          </Link>
        ))}
      </div>
      {data && data.data.length === 0 ? <EmptyState title="No batches created" description="Select approved orders to build a feasible route." action={<Link href="/manager/batches/new" className="btn btn-primary">Create the first batch</Link>} /> : null}
    </div>
  );
}
