import { AlertTriangle, ArrowUpRight, MessageSquareWarning } from "lucide-react";
import Link from "next/link";

import { IssueResolutionForm } from "@/components/admin/AdminActions";
import { SeverityBadge, StatusBadge } from "@/components/Status";
import { Callout, Card, EmptyState, PageHeader, StatCard } from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import { requireUser, serverFetchList } from "@/lib/server";
import type { Issue } from "@/lib/types";

export const metadata = { title: "Issue queue" };

export default async function AdminIssuesPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string; severity?: string }>;
}) {
  await requireUser("admin");
  const params = await searchParams;
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  if (params.severity) query.set("severity", params.severity);
  const { data: allIssues } = await serverFetchList<Issue>("/issues");
  const { data: issues } = await serverFetchList<Issue>(`/issues?${query.toString()}`);

  return (
    <div>
      <PageHeader
        eyebrow="Exceptions"
        title="Issue queue"
        description="Customer and partner reports sit beside the execution history. Resolving an issue never silently rewrites a parcel's status."
        actions={<Link href="/admin/analytics" className="btn btn-secondary">Estimated impact</Link>}
      />

      <div className="mb-5 grid gap-4 sm:grid-cols-3">
        <StatCard label="Open" value={allIssues.filter((issue) => issue.status === "open").length} hint="Needs triage" icon={<AlertTriangle size={17} aria-hidden />} tone="red" />
        <StatCard label="In review" value={allIssues.filter((issue) => issue.status === "in_review").length} hint="Assigned to dispatch" tone="amber" />
        <StatCard label="Resolved" value={allIssues.filter((issue) => issue.status === "resolved").length} hint="With a resolution note" tone="accent" />
      </div>

      <div className="mb-5 flex flex-wrap items-center gap-2">
        <Link href="/admin/issues" className={`btn btn-sm ${!params.status ? "btn-primary" : "btn-secondary"}`}>All</Link>
        {["open", "in_review", "resolved"].map((status) => (
          <Link
            key={status}
            href={`/admin/issues?status=${status}`}
            className={`btn btn-sm ${params.status === status ? "btn-primary" : "btn-secondary"} capitalize`}
          >
            {status.replaceAll("_", " ")}
          </Link>
        ))}
      </div>

      {issues.length === 0 ? (
        <EmptyState
          icon={<MessageSquareWarning size={20} aria-hidden />}
          title="No issues in this view"
          description="Reports from customers and partners appear here with their request, batch, severity and resolution history."
        />
      ) : (
        <div className="space-y-4">
          {issues.map((issue) => (
            <Card key={issue.id} className="card-pad">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="mono text-[11px] text-muted">ISSUE-{1000 + issue.id}</span>
                    <SeverityBadge severity={issue.severity} />
                    <StatusBadge status={issue.status} />
                    <span className="chip chip-neutral capitalize">{issue.category.replaceAll("_", " ")}</span>
                  </div>
                  <h2 className="mt-2 text-base font-semibold">{issue.description}</h2>
                  <p className="mt-1 text-[11px] text-muted">
                    Reported by {issue.reporter?.name ?? "unknown"} · {formatDateTime(issue.created_at)}
                  </p>
                </div>
                <div className="text-right text-[11px]">
                  {issue.request ? (
                    <Link
                      href={`/admin/requests?request=${issue.request.id}`}
                      className="inline-flex items-center gap-1 font-medium text-accent hover:underline"
                    >
                      {issue.request.code} <ArrowUpRight size={12} aria-hidden />
                    </Link>
                  ) : null}
                  {issue.batch ? (
                    <p className="mt-1">
                      <Link href={`/admin/batches?batch=${issue.batch.id}`} className="link mono">{issue.batch.code}</Link>
                    </p>
                  ) : null}
                  {issue.request?.customer_name ? (
                    <p className="mt-1 text-muted">{issue.request.customer_name}</p>
                  ) : null}
                </div>
              </div>

              <div className="mt-4 grid gap-4 border-t pt-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <div className="rounded-control bg-surface-muted p-3 text-[12px] leading-5 text-muted">
                  <p className="font-medium text-ink-2">Operational context</p>
                  <p className="mt-1">
                    {issue.batch
                      ? `Batch ${issue.batch.code} is ${issue.batch.status.replaceAll("_", " ")}.`
                      : "No batch is currently linked."}{" "}
                    {issue.request ? `Request status: ${issue.request.status.replaceAll("_", " ")}.` : ""}
                  </p>
                  {issue.resolution_note ? (
                    <p className="mt-1">Resolution note: {issue.resolution_note}</p>
                  ) : null}
                  {issue.resolved_by ? (
                    <p className="mt-1">Resolved by {issue.resolved_by.name} · {formatDateTime(issue.resolved_at)}</p>
                  ) : null}
                </div>
                <div>
                  <p className="mb-2 text-[12px] font-medium">Resolution action</p>
                  <IssueResolutionForm issue={issue} />
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      <div className="mt-5">
        <Callout tone="info" title="Issue handling is separate from execution truth">
          Marking a parcel failed happens through a validated status transition and opens an issue automatically. Resolving the
          issue documents the follow-up but does not fabricate a delivery or erase the parcel timeline.
        </Callout>
      </div>
    </div>
  );
}
