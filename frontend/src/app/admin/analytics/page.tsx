"use client";

import { useQuery } from "@tanstack/react-query";

import { CountBarChart } from "@/components/charts";
import { Callout, PageHeader, StatCard } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatKm, statusLabel } from "@/lib/format";
import type { AdminOverview } from "@/lib/types";

export default function AdminAnalyticsPage() {
  const analytics = useQuery({ queryKey: ["admin-analytics"], queryFn: () => apiGet<AdminOverview>("/admin/analytics") });
  const sustainability = useQuery({
    queryKey: ["admin-sustainability"],
    queryFn: () => apiGet<{
      totals: AdminOverview["sustainability"];
      methodology: string[];
      disclaimer: string;
      service_areas: AdminOverview["service_areas"];
    }>("/admin/analytics/sustainability"),
  });

  const data = analytics.data;
  const s = (sustainability.data?.totals ?? data?.sustainability) as AdminOverview["sustainability"] | undefined;
  const statusRows = Object.entries(data?.orders.by_status ?? {})
    .filter(([, count]) => count > 0)
    .map(([status, count]) => ({ label: statusLabel(status), value: count }));

  return (
    <div>
      <PageHeader eyebrow="Reports & sustainability" title="Platform analytics" description="Operational counts come from stored rows. Distance, fuel and CO₂e are modelled estimates with visible factors and methodology." />
      {analytics.isLoading ? <p className="text-sm text-muted">Loading analytics…</p> : null}
      {analytics.error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-[#8c2f2f]">{(analytics.error as Error).message}</p> : null}
      {data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Orders" value={data.orders.total} hint={`${data.orders.active} active`} />
            <StatCard label="Delivered" value={data.orders.delivered} hint={`${data.orders.failed} failed · ${data.orders.cancelled} cancelled`} tone="accent" />
            <StatCard label="Suggestion approval" value={data.matching.approval_rate_pct != null ? `${data.matching.approval_rate_pct}%` : "—"} hint={`${data.matching.suggestions} suggestions stored`} tone="blue" />
            <StatCard label="Average added detour" value={data.matching.average_added_detour_km != null ? formatKm(data.matching.average_added_detour_km, 2) : "—"} hint="Approved suggestions only" />
          </div>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Baseline distance" value={formatKm(s?.baseline_km ?? 0)} hint="Direct separate trips, modelled" />
            <StatCard label="Shared distance" value={formatKm(s?.shared_km ?? 0)} hint="Stored batch routes" />
            <StatCard label="Estimated saved" value={formatKm(s?.estimated_distance_saved_km ?? 0)} hint={`${s?.estimated_savings_percent ?? 0}% of baseline`} tone="accent" />
            <StatCard label="Estimated CO₂e avoided" value={`${(s?.estimated_co2e_avoided_kg ?? 0).toFixed(2)} kg`} hint={`${(s?.estimated_fuel_saved_l ?? 0).toFixed(2)} L fuel, modelled`} tone="blue" />
          </div>
          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            <div className="card card-pad">
              <h2 className="section-title">Orders by status</h2>
              <CountBarChart data={statusRows} />
              <ul className="mt-4 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                {statusRows.map((row) => <li key={row.label} className="flex justify-between border-b py-1 last:border-0"><span className="text-muted">{row.label}</span><span className="font-semibold">{row.value}</span></li>)}
              </ul>
            </div>
            <div className="card card-pad">
              <h2 className="section-title">Service areas</h2>
              <ul className="mt-3 space-y-1 text-sm">
                {data.service_areas.map((area) => <li key={area.id} className="flex justify-between border-b py-1 last:border-0"><span>{area.name}</span><span className="text-muted">{area.orders} orders · {area.drivers} drivers</span></li>)}
              </ul>
            </div>
          </div>
          <div className="mt-6">
            <Callout tone="warning" title="These are estimates, not telemetry">
              {sustainability.data?.disclaimer ?? data.disclaimer}
            </Callout>
          </div>
          {sustainability.data ? (
            <div className="card card-pad mt-4">
              <h2 className="section-title">Methodology</h2>
              <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm leading-6 text-muted">{sustainability.data.methodology.map((line) => <li key={line}>{line}</li>)}</ol>
              <p className="mt-3 text-xs text-muted">Factors: {s?.factors.fuel_l_per_km} L/km fuel; {s?.factors.kg_co2e_per_litre} kg CO₂e/L. Distance sources: {s?.distance_sources.join(", ") || "none measured"}.</p>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
