"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { PageHeader } from "@/components/ui";
import { StatusBadge } from "@/components/Status";
import { apiGetList } from "@/lib/api";
import type { BatchSummary } from "@/lib/types";

export default function ManagerProgressPage() {
  const { data } = useQuery({ queryKey: ["manager-batches"], queryFn: () => apiGetList<BatchSummary>("/manager/batches?per_page=100") });
  const rows = (data?.data ?? []).filter((batch) => batch.total_stops > 0);
  return (
    <div>
      <PageHeader eyebrow="Delivery progress" title="Stop completion by batch" description="Progress is counted from completed route stops, not from a decorative percentage." />
      <div className="space-y-3">
        {rows.map((batch) => {
          const pct = batch.total_stops ? Math.round((batch.completed_stops / batch.total_stops) * 100) : 0;
          return (
            <div key={batch.id} className="card card-pad">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Link href={`/manager/batches/${batch.id}`} className="font-semibold text-accent hover:underline">{batch.batch_number}</Link>
                <StatusBadge status={batch.status} />
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-muted"><div className="h-full bg-accent" style={{ width: `${pct}%` }} /></div>
              <p className="mt-1 text-xs text-muted">{batch.completed_stops} of {batch.total_stops} stops complete ({pct}%)</p>
            </div>
          );
        })}
      </div>
      {rows.length === 0 ? <p className="text-sm text-muted">No batch progress to show.</p> : null}
    </div>
  );
}
