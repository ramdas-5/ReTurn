"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button, ErrorText } from "@/components/ui-bits";
import { Card, Field, PageHeader } from "@/components/ui";
import { ApiError, apiGetList, apiPost } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { Issue } from "@/lib/types";

export default function SupportPage() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { data } = useQuery({
    queryKey: ["consumer-issues"],
    queryFn: () => apiGetList<Issue>("/issues"),
  });

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const form = new FormData(event.currentTarget);
    try {
      await apiPost("/issues", Object.fromEntries(form.entries()));
      await queryClient.invalidateQueries({ queryKey: ["consumer-issues"] });
      event.currentTarget.reset();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Issue could not be submitted.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1.1fr_1fr]">
      <div>
        <PageHeader eyebrow="Support & issues" title="Tell us what went wrong" description="Issues are reviewed by a manager responsible for the pickup area. They never silently change an order's delivery status." />
        <div className="space-y-3">
          {data?.data.map((issue) => (
            <Card key={issue.id}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold">{issue.subject}</p>
                  <p className="mt-1 text-[13px] text-muted">{issue.description}</p>
                  <p className="mt-1 text-[11px] text-muted">{issue.order_number ?? "General"} · {formatDateTime(issue.created_at)}</p>
                </div>
                <span className={`chip ${issue.status === "resolved" ? "chip-green" : issue.status === "in_review" ? "chip-blue" : "chip-amber"}`}>{issue.status.replaceAll("_", " ")}</span>
              </div>
              {issue.resolution_note ? <p className="mt-3 rounded-control bg-surface-muted p-2 text-xs">Resolution: {issue.resolution_note}</p> : null}
            </Card>
          ))}
          {data && data.data.length === 0 ? <p className="text-sm text-muted">No issues reported.</p> : null}
        </div>
      </div>
      <form onSubmit={submit} className="card card-pad space-y-3 self-start">
        <h2 className="section-title">Report an issue</h2>
        {error ? <ErrorText>{error}</ErrorText> : null}
        <Field label="Category">
          <select name="category" className="input" defaultValue="account">
            <option value="account">Account</option>
            <option value="delivery">Delivery</option>
            <option value="parcel">Parcel</option>
            <option value="pickup">Pickup</option>
            <option value="other">Other</option>
          </select>
        </Field>
        <Field label="Severity">
          <select name="severity" className="input" defaultValue="medium">
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </Field>
        <Field label="Subject"><input name="subject" className="input" required minLength={4} /></Field>
        <Field label="Description"><textarea name="description" className="input" rows={4} required minLength={10} /></Field>
        <Button type="submit" busy={busy}>Submit issue</Button>
      </form>
    </div>
  );
}
