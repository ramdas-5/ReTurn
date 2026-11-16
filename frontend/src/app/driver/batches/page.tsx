"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { EmptyState, PageHeader } from "@/components/ui";
import { StatusBadge } from "@/components/Status";
import { apiGetList } from "@/lib/api";
import { formatDateTime, formatKm } from "@/lib/format";
import type { BatchSummary } from "@/lib/types";

export default function DriverBatchesPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["driver-batches"],
    queryFn: () => apiGetList<BatchSummary>("/driver/batches"),
  });

  return (
    <div>
      <PageHeader eyebrow="Assigned batches" title="Your shared routes" description="A batch groups compatible orders into one ordered route. Each parcel keeps its own status and proof." />
      {isLoading ? <p className="text-sm text-muted">Loading batches…</p> : null}
      {error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-[#8c2f2f]">{(error as Error).message}</p> : null}
      <div className="grid gap-4 sm:grid-cols-2">
        {data?.data.map((batch) => (
          <Link key={batch.id} href={`/driver/batches/${batch.id}`} className="card card-pad hover:border-accent/50">
            <div className="flex items-start justify-between gap-2">
              <div><p className="font-bold">{batch.batch_number}</p><p className="text-sm text-muted">{batch.order_count} orders · {batch.total_stops} stops</p></div>
              <StatusBadge status={batch.status} />
            </div>
            <p className="mt-3 text-[13px] text-muted">{formatDateTime(batch.planned_start)} · {formatKm(batch.distance_km)}</p>
            <p className="mt-1 text-xs text-muted">{batch.completed_stops}/{batch.total_stops} stops completed</p>
          </Link>
        ))}
      </div>
      {data && data.data.length === 0 ? <EmptyState title="No batches yet" description="A manager creates and assigns batches before work reaches you." /> : null}
    </div>
  );
}
