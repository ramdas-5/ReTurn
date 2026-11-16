"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Radar } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button, ErrorText } from "@/components/ui-bits";
import { Card, EmptyState, PageHeader } from "@/components/ui";
import { ApiError, apiGetList, apiPost } from "@/lib/api";
import { formatKm } from "@/lib/format";
import type { MatchingSuggestion } from "@/lib/types";

export default function MatchingPage() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const suggestions = useQuery({
    queryKey: ["manager-suggestions"],
    queryFn: () => apiGetList<MatchingSuggestion>("/manager/matching/suggestions?status=all"),
  });

  async function scan() {
    setBusy("scan");
    setError(null);
    setMessage(null);
    try {
      const results = await apiPost<Array<{ suggestions_created: number; order: { order_number: string } }>>("/manager/matching/scan");
      setMessage(`Scanned ${results.length} approved orders · ${results.reduce((sum, row) => sum + row.suggestions_created, 0)} new suggestions.`);
      await queryClient.invalidateQueries({ queryKey: ["manager-suggestions"] });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Matching scan failed.");
    } finally {
      setBusy(null);
    }
  }

  async function decide(id: number, action: "approve" | "reject") {
    setBusy(`${action}-${id}`);
    setError(null);
    setMessage(null);
    try {
      if (action === "approve") {
        await apiPost(`/manager/matching/suggestions/${id}/approve`);
      } else {
        const reason = window.prompt("Reason for rejecting (5+ characters)");
        if (!reason) return;
        await apiPost(`/manager/matching/suggestions/${id}/reject`, { reason });
      }
      setMessage(`Suggestion ${action}d.`);
      await queryClient.invalidateQueries({ queryKey: ["manager-suggestions"] });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Decision failed.");
    } finally {
      setBusy(null);
    }
  }

  const rows = suggestions.data?.data ?? [];

  return (
    <div>
      <PageHeader
        eyebrow="Dynamic on-route matching"
        title="Fit new work into a route that is already moving"
        description="The scan evaluates active driver routes using real capacity, duty, service areas and stored route geometry. Nothing is auto-assigned: every suggestion needs a manager decision."
        actions={<Button busy={busy === "scan"} onClick={scan}><Radar size={15} aria-hidden /> Scan approved orders</Button>}
      />
      {error ? <ErrorText>{error}</ErrorText> : null}
      {message ? <p className="mb-4 rounded-control bg-accent-soft px-3 py-2 text-sm text-accent-strong">{message}</p> : null}
      {suggestions.isLoading ? <p className="text-sm text-muted">Loading suggestions…</p> : null}
      <div className="grid gap-4 lg:grid-cols-2">
        {rows.map((suggestion) => (
          <Card key={suggestion.id}>
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="font-semibold">{suggestion.order?.order_number ?? `Order ${suggestion.id}`}</p>
                <p className="text-sm text-muted">{suggestion.driver?.full_name ?? "Driver"} · {suggestion.order?.pickup.area} → {suggestion.order?.delivery.area}</p>
              </div>
              <span className={`chip ${suggestion.status === "pending" ? "chip-amber" : suggestion.status === "approved" ? "chip-green" : "chip-neutral"}`}>{suggestion.status}</span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-[13px]">
              <p>Detour <span className="font-semibold">{formatKm(suggestion.detour_km, 2)}</span></p>
              <p>Score <span className="font-semibold">{suggestion.score?.toFixed(1) ?? "—"}</span></p>
              <p>Added time <span className="font-semibold">{suggestion.added_duration_minutes?.toFixed(1) ?? "—"} min</span></p>
              <p>Source <span className="font-semibold">{suggestion.distance_source}</span></p>
            </div>
            {suggestion.reasons.length ? <p className="mt-2 text-xs leading-5 text-muted">{suggestion.reasons.map((reason) => reason.label).join(" · ")}</p> : null}
            {suggestion.blockers.length ? <p className="mt-2 text-xs text-danger">{suggestion.blockers.map((blocker) => blocker.label).join(" · ")}</p> : null}
            <div className="mt-3 flex flex-wrap gap-2">
              {suggestion.order ? <Link href={`/manager/orders/${suggestion.order.id}`} className="btn btn-secondary btn-sm">Open order</Link> : null}
              {suggestion.status === "pending" ? (
                <>
                  <Button className="btn btn-primary btn-sm" busy={busy === `approve-${suggestion.id}`} onClick={() => decide(suggestion.id, "approve")}>Approve</Button>
                  <Button className="btn btn-secondary btn-sm" busy={busy === `reject-${suggestion.id}`} onClick={() => decide(suggestion.id, "reject")}>Reject</Button>
                </>
              ) : null}
            </div>
          </Card>
        ))}
      </div>
      {suggestions.data && rows.length === 0 ? (
        <EmptyState
          icon={<Radar size={20} aria-hidden />}
          title="No suggestions stored yet"
          description="Approve pending orders, then run a scan. Feasible insertions will be persisted with their detour and capacity evidence."
          action={<Button busy={busy === "scan"} onClick={scan}>Run scan</Button>}
        />
      ) : null}
      {busy?.startsWith("approve") ? <p className="mt-3 inline-flex items-center gap-1 text-xs text-muted"><Loader2 size={13} className="animate-spin" aria-hidden /> Revalidating route…</p> : null}
    </div>
  );
}
