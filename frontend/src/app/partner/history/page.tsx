import { CheckCircle2, History, XCircle } from "lucide-react";
import Link from "next/link";

import { StatusBadge } from "@/components/Status";
import { Card, Callout, EmptyState, PageHeader, StatCard } from "@/components/ui";
import { formatDateTime, formatKm } from "@/lib/format";
import { requireUser, serverFetchList } from "@/lib/server";
import type { Batch, Issue } from "@/lib/types";

export const metadata = { title: "Completed work" };

export default async function PartnerHistoryPage() {
  await requireUser("partner");
  const [{ data: completed }, { data: exceptions }, { data: issues }] = await Promise.all([
    serverFetchList<Batch>("/batches?status=completed"),
    serverFetchList<Batch>("/batches?status=declined,cancelled"),
    serverFetchList<Issue>("/issues"),
  ]);

  const deliveredParcels = completed.reduce((total, batch) => total + batch.requests.length, 0);
  const estimatedSaved = completed.reduce((total, batch) => total + batch.savings_km, 0);

  return (
    <div>
      <PageHeader
        eyebrow="Work record"
        title="Completed work"
        description="Finished batches, declined or cancelled offers, and operational exceptions. Historical savings remain labelled estimates."
        actions={<Link href="/partner/batches" className="btn btn-secondary">Available batches</Link>}
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Completed batches" value={completed.length} hint="Delivered or fully resolved" icon={<CheckCircle2 size={17} aria-hidden />} tone="accent" />
        <StatCard label="Parcels in completed batches" value={deliveredParcels} hint="Independent parcel histories" icon={<History size={17} aria-hidden />} />
        <StatCard label="Estimated distance saved" value={formatKm(estimatedSaved)} hint="Modelled, not measured" icon={<CheckCircle2 size={17} aria-hidden />} tone="blue" />
      </div>

      <section className="mt-7">
        <h2 className="section-title">Delivered batches</h2>
        {completed.length === 0 ? (
          <div className="mt-3">
            <EmptyState
              icon={<CheckCircle2 size={20} aria-hidden />}
              title="No completed work yet"
              description="Accepted and fully executed batches will appear here with their individual parcel outcomes."
            />
          </div>
        ) : (
          <div className="mt-3 space-y-3">
            {completed.map((batch) => (
              <Card key={batch.id} className="card-pad">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="mono text-[12px]">{batch.code}</span>
                      <StatusBadge status={batch.status} />
                    </div>
                    <p className="mt-1 text-[12px] text-muted">
                      {batch.requests.length} parcels · {batch.stops.length} stops · completed{" "}
                      {formatDateTime(batch.completed_at ?? batch.created_at)}
                    </p>
                    <ul className="mt-2 space-y-1">
                      {batch.requests.map((request) => (
                        <li key={request.id} className="text-[12px]">
                          <span className="mono text-[11px] text-muted">{request.code}</span> · {request.parcel.description}{" "}
                          <span className="text-muted">({request.parcel.status.replaceAll("_", " ")})</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="text-right text-[12px]">
                    <p className="text-muted">Estimated saving</p>
                    <p className="mono text-lg font-semibold text-accent-strong">{batch.savings_percent.toFixed(1)}%</p>
                    <p className="text-muted">{formatKm(batch.distance_km)} shared</p>
                    <Link href={`/partner/batches/${batch.id}`} className="btn btn-secondary btn-sm mt-2">View record</Link>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </section>

      <section className="mt-8 grid gap-5 lg:grid-cols-2">
        <div>
          <h2 className="section-title">Declined or cancelled</h2>
          {exceptions.length === 0 ? (
            <p className="mt-2 rounded-card border border-dashed bg-surface px-4 py-6 text-sm text-muted">
              No declined or cancelled assignments recorded.
            </p>
          ) : (
            <ul className="mt-3 space-y-2">
              {exceptions.map((batch) => (
                <li key={batch.id} className="card flex items-start justify-between gap-3 p-4">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="mono text-[12px]">{batch.code}</span>
                      <StatusBadge status={batch.status} />
                    </div>
                    <p className="mt-1 text-[12px] leading-5 text-muted">
                      {batch.declined_reason ?? batch.cancelled_reason ?? "No reason recorded."}
                    </p>
                    <p className="text-[11px] text-muted">{formatDateTime(batch.created_at)}</p>
                  </div>
                  <XCircle size={17} className="shrink-0 text-muted" aria-hidden />
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <h2 className="section-title">Issues on your work</h2>
          {issues.length === 0 ? (
            <p className="mt-2 rounded-card border border-dashed bg-surface px-4 py-6 text-sm text-muted">
              No issues reported on your batches.
            </p>
          ) : (
            <ul className="mt-3 space-y-2">
              {issues.map((issue) => (
                <li key={issue.id} className="card p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="mono text-[11px]">{issue.request?.code ?? `Issue #${issue.id}`}</span>
                    <span className={`chip ${issue.status === "resolved" ? "chip-green" : "chip-amber"}`}>
                      {issue.status.replaceAll("_", " ")}
                    </span>
                  </div>
                  <p className="mt-1 text-[12px] leading-5 text-muted">{issue.description}</p>
                  {issue.resolution_note ? (
                    <p className="mt-1 text-[11px] text-muted">Resolution: {issue.resolution_note}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <div className="mt-6">
        <Callout tone="warning" title="Historical estimates stay estimates">
          Completed work shows modelled distance and fuel figures. They are not proof of measured emissions or guaranteed
          trip removal.
        </Callout>
      </div>
    </div>
  );
}
