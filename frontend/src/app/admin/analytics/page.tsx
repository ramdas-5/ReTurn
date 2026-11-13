import { BarChart3, Leaf, Route, TrendingDown } from "lucide-react";

import { SourceBadge } from "@/components/SavingsPanel";
import { Callout, Card, PageHeader, StatCard } from "@/components/ui";
import { formatKm } from "@/lib/format";
import { requireUser, serverFetch } from "@/lib/server";
import type { AnalyticsSummary, Sustainability } from "@/lib/types";

export const metadata = { title: "Analytics & estimated impact" };

export default async function AdminAnalyticsPage() {
  await requireUser("admin");
  const [summary, sustainability] = await Promise.all([
    serverFetch<AnalyticsSummary>("/analytics/summary"),
    serverFetch<Sustainability>("/analytics/sustainability"),
  ]);

  const maxVolume = Math.max(1, ...summary.request_volume.map((item) => item.count));
  const maxBatchKm = Math.max(1, ...sustainability.batches.map((batch) => batch.baseline_km));
  const averageRequestsPerBatch =
    sustainability.batches.length > 0
      ? sustainability.batches.reduce((total, batch) => total + batch.request_count, 0) /
        sustainability.batches.length
      : 0;

  return (
    <div>
      <PageHeader
        eyebrow="Reporting"
        title="Operations & estimated impact"
        description="Operational throughput and a transparent, estimate-only sustainability model. The baseline and shared-plan figures use the same distance basis and stated factors."
        actions={<span className="chip chip-amber">{sustainability.labelled} figures</span>}
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Estimated distance saved" value={formatKm(sustainability.totals.estimated_distance_saved_km)} hint="Modelled, not measured" icon={<Leaf size={17} aria-hidden />} tone="accent" />
        <StatCard label="Estimated fuel saved" value={`${sustainability.totals.estimated_fuel_saved_l.toFixed(1)} L`} hint="Configurable fuel factor" icon={<TrendingDown size={17} aria-hidden />} tone="amber" />
        <StatCard label="Estimated CO₂e avoided" value={`${sustainability.totals.estimated_co2e_avoided_kg.toFixed(1)} kg`} hint="Not verified emissions" icon={<Leaf size={17} aria-hidden />} tone="blue" />
        <StatCard label="Average batch saving" value={`${summary.average_savings_percent.toFixed(1)}%`} hint={`${sustainability.totals.batches} committed batches`} icon={<Route size={17} aria-hidden />} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <Card className="card-pad">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="section-title">Before vs shared plan</h2>
              <p className="mt-1 text-sm text-muted">
                Same set of committed batches, same estimation basis. Bars scale to the largest baseline in this view.
              </p>
            </div>
            <SourceBadge source={sustainability.batches[0]?.distance_source ?? "estimated"} />
          </div>
          <div className="mt-5 space-y-4">
            {sustainability.batches.length === 0 ? (
              <p className="text-sm text-muted">No committed batches yet. Create a feasible proposal to start this report.</p>
            ) : (
              sustainability.batches.slice(0, 8).map((batch) => (
                <div key={batch.batch_id}>
                  <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2 text-[11px]">
                    <span className="mono font-medium">{batch.code}</span>
                    <span className="text-muted">
                      {batch.request_count} requests · {batch.distance_source === "osrm" ? "OSRM" : "estimated"}
                    </span>
                  </div>
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2">
                      <span className="w-[74px] shrink-0 text-[10px] uppercase tracking-wide text-muted">Baseline</span>
                      <div className="h-3 flex-1 overflow-hidden rounded-full bg-surface-muted">
                        <div
                          className="h-full rounded-full bg-[#9fb3ad]"
                          style={{ width: `${Math.max(2, (batch.baseline_km / maxBatchKm) * 100)}%` }}
                        />
                      </div>
                      <span className="mono w-16 text-right text-[11px]">{formatKm(batch.baseline_km)}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="w-[74px] shrink-0 text-[10px] uppercase tracking-wide text-muted">Shared</span>
                      <div className="h-3 flex-1 overflow-hidden rounded-full bg-surface-muted">
                        <div
                          className="h-full rounded-full bg-accent"
                          style={{ width: `${Math.max(2, (batch.shared_km / maxBatchKm) * 100)}%` }}
                        />
                      </div>
                      <span className="mono w-16 text-right text-[11px]">{formatKm(batch.shared_km)}</span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
          <div className="mt-5 flex flex-wrap gap-2 border-t pt-4">
            <span className="chip chip-green">Estimated saving {formatKm(sustainability.totals.estimated_distance_saved_km)}</span>
            <span className="chip chip-amber">{sustainability.totals.estimated_savings_percent.toFixed(1)}% modelled</span>
            <span className="chip chip-neutral">{averageRequestsPerBatch.toFixed(1)} requests / batch</span>
          </div>
        </Card>

        <Card className="card-pad">
          <h2 className="section-title">Request volume</h2>
          {summary.request_volume.length === 0 ? (
            <p className="mt-3 text-sm text-muted">No requests in this window.</p>
          ) : (
            <div className="mt-5 flex h-40 items-end gap-2" role="img" aria-label="Request volume bar chart">
              {summary.request_volume.map((item) => (
                <div key={item.day} className="flex min-w-0 flex-1 flex-col items-center gap-1.5">
                  <span className="text-[9px] text-muted">{item.count}</span>
                  <div
                    className="w-full rounded-t bg-[#2c6ca2]/80"
                    style={{ height: `${Math.max(4, (item.count / maxVolume) * 100)}%` }}
                    title={`${item.count} requests on ${item.day}`}
                  />
                  <span className="text-[8px] text-muted">{item.day.slice(5)}</span>
                </div>
              ))}
            </div>
          )}
          <div className="mt-4 grid gap-2 border-t pt-4 text-[12px]">
            <div className="flex justify-between gap-2">
              <span className="text-muted">Completed requests</span>
              <span className="mono font-medium">{summary.completed_requests}</span>
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-muted">Completed parcels</span>
              <span className="mono font-medium">{summary.completed_parcels}</span>
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-muted">Service mix</span>
              <span className="mono font-medium">
                {summary.service_mix.map((entry) => `${entry.type === "return" ? "R" : "P"}:${entry.count}`).join(" · ") || "—"}
              </span>
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-muted">Open issues</span>
              <span className="mono font-medium">{summary.open_issues}</span>
            </div>
          </div>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <Card className="overflow-hidden">
          <div className="flex items-center justify-between gap-3 border-b px-5 py-4">
            <div>
              <h2 className="section-title">Batch estimate ledger</h2>
              <p className="text-[11px] text-muted">Every committed batch, with its source and modelled factors.</p>
            </div>
            <BarChart3 size={18} className="text-muted" aria-hidden />
          </div>
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Batch</th>
                  <th scope="col">Requests</th>
                  <th scope="col">Baseline</th>
                  <th scope="col">Shared</th>
                  <th scope="col">Est. saved</th>
                  <th scope="col">Est. fuel</th>
                  <th scope="col">Est. CO₂e</th>
                  <th scope="col">Source</th>
                </tr>
              </thead>
              <tbody>
                {sustainability.batches.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="text-center text-muted">No batches yet.</td>
                  </tr>
                ) : (
                  sustainability.batches.map((batch) => (
                    <tr key={batch.batch_id}>
                      <td className="mono text-[11px]">{batch.code}</td>
                      <td>{batch.request_count}</td>
                      <td className="mono text-[11px]">{batch.baseline_km.toFixed(1)} km</td>
                      <td className="mono text-[11px]">{batch.shared_km.toFixed(1)} km</td>
                      <td className="mono text-[11px] font-medium text-accent-strong">{batch.saved_km.toFixed(1)} km</td>
                      <td className="mono text-[11px]">{batch.estimated_fuel_saved_l.toFixed(2)} L</td>
                      <td className="mono text-[11px]">{batch.estimated_co2e_avoided_kg.toFixed(2)} kg</td>
                      <td className="text-[11px]">{batch.distance_source === "osrm" ? "OSRM" : "Estimated"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>

        <div className="space-y-5">
          <Card className="card-pad">
            <h2 className="section-title">Methodology & factors</h2>
            <dl className="mt-3 space-y-2 text-[12px]">
              <div className="flex justify-between gap-2">
                <dt className="text-muted">Fuel factor</dt>
                <dd className="mono">{sustainability.factors.fuel_l_per_km.toFixed(2)} L/km</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted">CO₂e factor</dt>
                <dd className="mono">{sustainability.factors.kg_co2e_per_litre.toFixed(2)} kg/L</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted">Measured emissions?</dt>
                <dd className="font-medium">No — modelled</dd>
              </div>
            </dl>
            <ul className="mt-4 space-y-2 border-t pt-3 text-[11px] leading-5 text-muted">
              {sustainability.methodology.map((item) => (
                <li key={item}>• {item}</li>
              ))}
            </ul>
          </Card>

          <Callout tone="warning" title="Read this before quoting a number">
            {sustainability.disclaimer} A negative or zero raw distance delta is clamped to zero benefit rather than being
            presented as a positive saving.
          </Callout>

          <Card className="card-pad">
            <h2 className="section-title">Batch utilisation</h2>
            <div className="mt-3 space-y-3 text-[12px]">
              <div className="flex items-center justify-between gap-2">
                <span className="text-muted">Batches reported</span>
                <span className="mono font-medium">{sustainability.totals.batches}</span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-muted">Avg requests per batch</span>
                <span className="mono font-medium">{averageRequestsPerBatch.toFixed(1)}</span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-muted">Baseline distance</span>
                <span className="mono font-medium">{formatKm(sustainability.totals.baseline_km)}</span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-muted">Shared distance</span>
                <span className="mono font-medium">{formatKm(sustainability.totals.shared_km)}</span>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
