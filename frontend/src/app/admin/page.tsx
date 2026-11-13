import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ClipboardList,
  Layers,
  MapPin,
  Navigation,
  ShieldCheck,
  Sparkles,
  UserPlus,
} from "lucide-react";
import Link from "next/link";

import { BatchMap } from "@/components/BatchStops";
import { StatusBadge } from "@/components/Status";
import { Callout, Card, EmptyState, PageHeader, StatCard } from "@/components/ui";
import { formatDateTime, formatKm } from "@/lib/format";
import { requireUser, serverFetch } from "@/lib/server";
import type { AnalyticsSummary, Batch, PartnerProfile } from "@/lib/types";

export const metadata = { title: "Operations overview" };

type AdminOverview = AnalyticsSummary & {
  pending_partners: PartnerProfile[];
  recent_audit: Array<{
    id: number;
    action: string;
    summary: string;
    actor_name: string;
    actor_role: string;
    created_at: string;
  }>;
  active_batches: Batch[];
};

export default async function AdminDashboard() {
  await requireUser("admin");
  const data = await serverFetch<AdminOverview>("/admin/overview");
  const liveBatch = data.active_batches[0];
  const maxVolume = Math.max(1, ...data.request_volume.map((item) => item.count));

  return (
    <div>
      <PageHeader
        eyebrow="Dispatch control room"
        title="Operations overview"
        description="Queue health, feasible proposals, route execution and estimated impact in one place. Every action is authorized by the API and recorded."
        actions={
          <>
            <Link href="/admin/batches#matching" className="btn btn-primary">
              <Sparkles size={16} aria-hidden /> Run smart matching
            </Link>
            <Link href="/admin/analytics" className="btn btn-secondary">
              Estimated impact
            </Link>
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Pending requests"
          value={data.pending_requests}
          hint={`${data.request_counts.batched ?? 0} already reserved in proposals`}
          icon={<ClipboardList size={17} aria-hidden />}
          tone="accent"
        />
        <StatCard
          label="Proposed batches"
          value={data.proposed_batches}
          hint={`${data.batch_counts.offered ?? 0} offers awaiting partner decision`}
          icon={<Layers size={17} aria-hidden />}
          tone="blue"
        />
        <StatCard
          label="Active routes"
          value={data.active_routes}
          hint="Accepted or in progress"
          icon={<Navigation size={17} aria-hidden />}
          tone="amber"
        />
        <StatCard
          label="Completed parcels"
          value={data.completed_parcels}
          hint={`${data.failed_parcels} failed parcel${data.failed_parcels === 1 ? "" : "s"} recorded`}
          icon={<CheckCircle2 size={17} aria-hidden />}
        />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        <Card className="card-pad">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="section-title">Matching queue</h2>
              <p className="mt-1 text-sm text-muted">
                {data.pending_requests} requests await a run. Nearby alone never creates a batch; feasibility is
                recalculated on commit.
              </p>
            </div>
            <Link href="/admin/batches#matching" className="btn btn-primary btn-sm">
              Open matching console <ArrowRight size={14} aria-hidden />
            </Link>
          </div>
          <div className="mt-4 space-y-2">
            {data.active_batches.length === 0 ? (
              <EmptyState
                icon={<Layers size={19} aria-hidden />}
                title="No proposals in flight"
                description="Run matching to inspect feasible groups and the reasons nearby requests were rejected."
              />
            ) : (
              data.active_batches.slice(0, 4).map((batch) => (
                <Link
                  key={batch.id}
                  href={`/admin/batches?batch=${batch.id}`}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-control border bg-surface px-4 py-3 transition hover:bg-surface-muted"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="mono text-[12px] font-medium">{batch.code}</span>
                      <StatusBadge status={batch.status} />
                    </div>
                    <p className="mt-1 text-[12px] text-muted">
                      {(batch.request_count ?? batch.requests.length)} requests ·{" "}
                      {batch.partner?.name ?? "Unassigned"} · estimated {formatKm(batch.savings_km)} saved
                    </p>
                  </div>
                  <span className="text-[11px] text-muted">{formatDateTime(batch.created_at)}</span>
                </Link>
              ))
            )}
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 border-t pt-4 text-[11px] text-muted">
            <span>Average estimated saving {data.average_savings_percent.toFixed(1)}%</span>
            <span>{data.customers} customers · {data.partners} partners</span>
          </div>
        </Card>

        <div className="space-y-6">
          <Card className="overflow-hidden">
            <div className="flex items-center justify-between gap-2 border-b px-5 py-4">
              <h2 className="section-title">Route overview</h2>
              {liveBatch ? <StatusBadge status={liveBatch.status} /> : null}
            </div>
            <div className="p-4">
              {liveBatch ? (
                <>
                  <BatchMap batch={liveBatch} height="240px" />
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                    <p className="text-[12px] font-medium">{liveBatch.code} · {liveBatch.stops.length} stops</p>
                    <Link href="/admin/routes" className="text-[11px] font-medium text-accent hover:underline">
                      Route monitor
                    </Link>
                  </div>
                </>
              ) : (
                <div className="flex h-[240px] items-center justify-center rounded-control border border-dashed bg-surface-muted px-6 text-center text-sm text-muted">
                  No active batch to map. Feasible proposals will appear here after a matching run.
                </div>
              )}
            </div>
          </Card>

          <Card className="card-pad">
            <div className="flex items-center justify-between gap-2">
              <h2 className="section-title">Partner verification</h2>
              <ShieldCheck size={18} className="text-accent" aria-hidden />
            </div>
            {data.pending_partners.length === 0 ? (
              <p className="mt-2 text-sm text-muted">No partner accounts are waiting for verification.</p>
            ) : (
              <ul className="mt-3 space-y-2">
                {data.pending_partners.map((profile) => (
                  <li key={profile.id} className="flex items-start justify-between gap-2 rounded-control bg-surface-muted px-3 py-2.5">
                    <div>
                      <p className="text-[13px] font-medium">{profile.name}</p>
                      <p className="text-[11px] text-muted">
                        {profile.company_name} · <span className="capitalize">{profile.vehicle_type}</span>
                      </p>
                    </div>
                    <Link href="/admin/partners" className="text-[11px] font-medium text-accent hover:underline">
                      Review
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            <Link href="/admin/partners" className="btn btn-secondary btn-sm mt-3 w-full">
              <UserPlus size={14} aria-hidden /> Manage partners
            </Link>
          </Card>
        </div>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <Card className="card-pad">
          <div className="flex items-end justify-between gap-3">
            <div>
              <h2 className="section-title">Request volume</h2>
              <p className="mt-1 text-sm text-muted">New requests over the recent window.</p>
            </div>
            <span className="chip chip-neutral">Last 14 days</span>
          </div>
          {data.request_volume.length === 0 ? (
            <p className="mt-6 text-sm text-muted">No requests recorded in this window.</p>
          ) : (
            <div className="mt-6 flex h-44 items-end gap-2" role="img" aria-label="Bar chart of recent request volume">
              {data.request_volume.map((item) => (
                <div key={item.day} className="flex min-w-0 flex-1 flex-col items-center gap-2">
                  <span className="text-[10px] text-muted">{item.count}</span>
                  <div
                    className="w-full rounded-t bg-accent/80"
                    style={{ height: `${Math.max(4, (item.count / maxVolume) * 100)}%` }}
                    title={`${item.count} requests on ${item.day}`}
                  />
                  <span className="text-[9px] text-muted">{item.day.slice(5)}</span>
                </div>
              ))}
            </div>
          )}
          <div className="mt-5 grid gap-3 border-t pt-4 text-[12px] sm:grid-cols-3">
            {data.service_mix.map((entry) => (
              <div key={entry.type} className="flex items-center justify-between gap-2">
                <span className="text-muted">{entry.type === "return" ? "Product returns" : "Parcel deliveries"}</span>
                <span className="mono font-medium">{entry.count}</span>
              </div>
            ))}
            <div className="flex items-center justify-between gap-2">
              <span className="text-muted">Completed requests</span>
              <span className="mono font-medium">{data.completed_requests}</span>
            </div>
          </div>
        </Card>

        <div className="space-y-6">
          <Card className="card-pad">
            <div className="flex items-center justify-between gap-2">
              <h2 className="section-title">Unresolved issues</h2>
              <AlertTriangle size={17} className="text-[#8a5a12]" aria-hidden />
            </div>
            {data.recent_issues.length === 0 ? (
              <p className="mt-2 text-sm text-muted">No open issues. Good route hygiene.</p>
            ) : (
              <ul className="mt-3 space-y-2">
                {data.recent_issues.map((issue) => (
                  <li key={issue.id} className="rounded-control border bg-surface-muted px-3 py-2.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="mono text-[11px]">{issue.request_code ?? `Issue #${issue.id}`}</span>
                      <span className="chip chip-amber capitalize">{issue.severity}</span>
                    </div>
                    <p className="mt-1 text-[12px] capitalize text-muted">{issue.category.replaceAll("_", " ")}</p>
                  </li>
                ))}
              </ul>
            )}
            <Link href="/admin/issues" className="btn btn-secondary btn-sm mt-3 w-full">
              Open issue queue
            </Link>
          </Card>

          <Card className="card-pad">
            <h2 className="section-title">Recent dispatch actions</h2>
            {data.recent_audit.length === 0 ? (
              <p className="mt-2 text-sm text-muted">No audit events yet.</p>
            ) : (
              <ol className="mt-3 space-y-3">
                {data.recent_audit.slice(0, 5).map((event) => (
                  <li key={event.id} className="border-l-2 border-line pl-3">
                    <p className="text-[12px] leading-5">{event.summary}</p>
                    <p className="text-[10px] text-muted">
                      {formatDateTime(event.created_at)} · {event.actor_name} ({event.actor_role})
                    </p>
                  </li>
                ))}
              </ol>
            )}
          </Card>
        </div>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-4 rounded-card border bg-surface px-5 py-4 text-[12px] text-muted">
        <span className="inline-flex items-center gap-1.5"><MapPin size={14} aria-hidden /> All map routes are planned estimates, not live GPS.</span>
        <span className="inline-flex items-center gap-1.5"><ShieldCheck size={14} aria-hidden /> Only verified partners are offered work.</span>
        <span className="inline-flex items-center gap-1.5"><AlertTriangle size={14} aria-hidden /> Failed parcels open an issue automatically.</span>
      </div>
      <div className="mt-3">
        <Callout tone="warning" title="Estimated impact disclosure">
          {data.disclaimer}
        </Callout>
      </div>
    </div>
  );
}
