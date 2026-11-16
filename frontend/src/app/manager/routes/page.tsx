"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { PageHeader } from "@/components/ui";
import { StatusBadge } from "@/components/Status";
import { apiGetList } from "@/lib/api";
import { formatKm } from "@/lib/format";
import type { BatchSummary } from "@/lib/types";

export default function ManagerRoutesPage() {
  const { data } = useQuery({ queryKey: ["manager-batches"], queryFn: () => apiGetList<BatchSummary>("/manager/batches?per_page=100") });
  const active = (data?.data ?? []).filter((batch) => ["assigned", "active"].includes(batch.status));
  return (
    <div>
      <PageHeader eyebrow="Route management" title="Routes currently in play" description="Open a batch to inspect its ordered stops, distance basis and driver." />
      <div className="grid gap-4 sm:grid-cols-2">
        {active.map((batch) => (
          <Link key={batch.id} href={`/manager/batches/${batch.id}`} className="card card-pad hover:border-accent/50">
            <div className="flex items-center justify-between gap-2"><p className="font-bold">{batch.batch_number}</p><StatusBadge status={batch.status} /></div>
            <p className="mt-2 text-sm text-muted">{batch.driver?.full_name ?? "No driver"} · {formatKm(batch.distance_km)} · {batch.distance_source}</p>
            <p className="mt-1 text-xs text-muted">{batch.completed_stops}/{batch.total_stops} stops completed</p>
          </Link>
        ))}
      </div>
      {active.length === 0 ? <p className="text-sm text-muted">No assigned or active routes right now.</p> : null}
    </div>
  );
}
