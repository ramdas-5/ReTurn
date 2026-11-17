"use client";

import { useQuery } from "@tanstack/react-query";

import { ExceptionReview, IssueReview } from "@/components/ReviewActions";
import { Card, PageHeader } from "@/components/ui";
import { apiGetList } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { DeliveryException, Issue } from "@/lib/types";

export default function ManagerIssuesPage() {
  const exceptions = useQuery({
    queryKey: ["exceptions", "manager"],
    queryFn: () => apiGetList<DeliveryException>("/manager/exceptions?per_page=50"),
  });
  const issues = useQuery({
    queryKey: ["issues", "manager"],
    queryFn: () => apiGetList<Issue>("/issues?status=open"),
  });

  return (
    <div>
      <PageHeader eyebrow="Delivery issues" title="Resolve blockers without hiding them" description="Exceptions and consumer reports are separate from order status. Resolving one records a reason and reviewer; it does not fake a delivery." />
      <section>
        <h2 className="section-title mb-3">Driver exceptions</h2>
        {exceptions.isLoading ? <p className="text-sm text-muted">Loading exceptions…</p> : null}
        {exceptions.error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-red-ink">{(exceptions.error as Error).message}</p> : null}
        <div className="space-y-3">
          {exceptions.data?.data.map((row) => (
            <Card key={row.id}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold">{row.order_number} · {row.exception_type.replaceAll("_", " ")}</p>
                  <p className="mt-1 text-sm text-muted">{row.description}</p>
                  <p className="mt-1 text-xs text-muted">{row.driver?.full_name ?? "Driver"} · {formatDateTime(row.created_at)}</p>
                </div>
                <span className={`chip ${row.status === "resolved" ? "chip-green" : row.status === "rejected" ? "chip-neutral" : "chip-amber"}`}>{row.status}</span>
              </div>
              {row.status === "open" ? <ExceptionReview exceptionId={row.id} scope="manager" /> : row.resolution_note ? <p className="mt-2 rounded-control bg-surface-tint p-2 text-xs">Resolution: {row.resolution_note}</p> : null}
            </Card>
          ))}
          {exceptions.data && exceptions.data.data.length === 0 ? <p className="text-sm text-muted">No delivery exceptions.</p> : null}
        </div>
      </section>

      <section className="mt-8">
        <h2 className="section-title mb-3">Consumer reports</h2>
        <div className="space-y-3">
          {issues.data?.data.map((issue) => (
            <Card key={issue.id}>
              <div className="flex items-start justify-between gap-3">
                <div><p className="font-semibold">{issue.subject}</p><p className="mt-1 text-sm text-muted">{issue.description}</p><p className="mt-1 text-xs text-muted">{issue.order_number ?? "General"} · {issue.reporter?.full_name}</p></div>
                <span className="chip chip-amber">{issue.severity}</span>
              </div>
              <IssueReview issueId={issue.id} />
            </Card>
          ))}
          {issues.data && issues.data.data.length === 0 ? <p className="text-sm text-muted">No open consumer reports.</p> : null}
        </div>
      </section>
    </div>
  );
}
