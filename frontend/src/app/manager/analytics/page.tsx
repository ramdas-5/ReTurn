"use client";

import { useQuery } from "@tanstack/react-query";

import { SharePieChart } from "@/components/charts";
import { PageHeader, StatCard } from "@/components/ui";
import { apiGet, apiGetList } from "@/lib/api";
import { formatKm, statusLabel } from "@/lib/format";
import type { BatchSummary, ManagerSummary, MatchingSuggestion } from "@/lib/types";

export default function ManagerAnalyticsPage() {
  const summary = useQuery({ queryKey: ["manager-summary"], queryFn: () => apiGet<ManagerSummary>("/manager/summary") });
  const batches = useQuery({ queryKey: ["manager-batches"], queryFn: () => apiGetList<BatchSummary>("/manager/batches?per_page=100") });
  const suggestions = useQuery({ queryKey: ["manager-suggestions"], queryFn: () => apiGetList<MatchingSuggestion>("/manager/matching/suggestions?status=all") });

  const rows = batches.data?.data ?? [];
  const totalKm = rows.reduce((sum, row) => sum + (row.distance_km || 0), 0);
  const approved = (suggestions.data?.data ?? []).filter((row) => row.status === "approved").length;
  const pending = (suggestions.data?.data ?? []).filter((row) => row.status === "pending").length;
  const suggestionRows = Object.entries(
    (suggestions.data?.data ?? []).reduce<Record<string, number>>((acc, row) => {
      acc[row.status] = (acc[row.status] ?? 0) + 1;
      return acc;
    }, {}),
  ).map(([status, count]) => ({ label: statusLabel(status), value: count }));

  return (
    <div>
      <PageHeader eyebrow="Reports" title="Your operational record" description="Counts and distances below are read from stored orders, batches and suggestions. No dashboard figures are hardcoded." />
      {summary.data ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Delivered today" value={summary.data.orders.delivered_today} hint="Completed with proof rules applied" />
          <StatCard label="Active orders" value={summary.data.orders.active} hint={`${summary.data.orders.delayed} past deadline`} />
          <StatCard label="Batches" value={summary.data.batches.total} hint={`${summary.data.batches.active} active`} />
          <StatCard label="Open exceptions" value={summary.data.exceptions.open} hint="Awaiting a decision" />
        </div>
      ) : null}
      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <StatCard label="Batch route distance" value={formatKm(totalKm)} hint="Sum of stored route distances in scope" />
        <StatCard label="Approved suggestions" value={approved} hint={`${pending} still pending`} />
        <StatCard label="Drivers with active batch" value={summary.data?.drivers.with_active_batch ?? 0} />
      </div>
      <div className="card card-pad mt-6">
        <h2 className="section-title">Suggestion outcomes</h2>
        <p className="mt-1 text-xs text-muted">Counted from stored suggestions for orders in your service areas.</p>
        <SharePieChart data={suggestionRows} />
      </div>
      <div className="card card-pad mt-6">
        <h2 className="section-title">Batches in scope</h2>
        <div className="table-wrap mt-3">
          <div className="table-scroll">
            <table className="data-table">
              <thead><tr><th>Batch</th><th>Driver</th><th>Orders</th><th>Distance</th><th>Completed stops</th></tr></thead>
              <tbody>
                {rows.map((row) => <tr key={row.id}><td className="font-medium">{row.batch_number}</td><td>{row.driver?.full_name ?? "—"}</td><td>{row.order_count}</td><td>{formatKm(row.distance_km)}</td><td>{row.completed_stops}/{row.total_stops}</td></tr>)}
              </tbody>
            </table>
          </div>
        </div>
      </div>
      <p className="mt-4 text-xs leading-5 text-muted">Distance figures are route-planning outputs and may be OSRM road distances or clearly labelled estimates. ReTurn does not claim measured fuel or CO₂ savings here.</p>
    </div>
  );
}
