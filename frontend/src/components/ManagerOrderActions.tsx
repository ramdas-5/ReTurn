"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";

import { ApiError, apiGetList, apiPost } from "@/lib/api";
import { Button, ErrorText } from "@/components/ui-bits";

type DriverRow = {
  driver: { id: number; full_name: string; phone: string | null };
  duty_label: string;
  is_live: boolean;
  active_batch: { id: number } | null;
};

type Suggestion = {
  id: number;
  driver: { full_name: string } | null;
  detour_km: number | null;
  score: number | null;
  reasons: Array<{ label: string }>;
};

export default function ManagerOrderActions({
  orderId,
  status,
  suggestions = [],
}: {
  orderId: number;
  status: string;
  suggestions?: Suggestion[];
}) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const { data: drivers } = useQuery({
    queryKey: ["manager-drivers"],
    queryFn: () => apiGetList<DriverRow>("/manager/drivers"),
  });

  async function run(key: string, path: string, body: unknown, note: string) {
    setBusy(key);
    setError(null);
    setMessage(null);
    try {
      await apiPost(path, body);
      setMessage(note);
      await queryClient.invalidateQueries({ queryKey: ["manager-order", String(orderId)] });
      await queryClient.invalidateQueries({ queryKey: ["manager-orders"] });
      await queryClient.invalidateQueries({ queryKey: ["manager-suggestions"] });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Action failed.");
    } finally {
      setBusy(null);
    }
  }

  async function review(event: React.FormEvent<HTMLFormElement>, decision: "approve" | "reject") {
    event.preventDefault();
    const reason = String(new FormData(event.currentTarget).get("reason") ?? "");
    await run(decision, `/manager/orders/${orderId}/review`, { decision, reason }, `Order ${decision}d.`);
  }

  async function assign(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await run("assign", `/manager/orders/${orderId}/assign`, {
      driver_id: Number(form.get("driver_id")),
      reason: form.get("reason") || undefined,
    }, "Driver assigned.");
  }

  return (
    <div className="space-y-4">
      {error ? <ErrorText>{error}</ErrorText> : null}
      {message ? <p className="rounded-control bg-accent-soft px-3 py-2 text-sm text-accent-strong">{message}</p> : null}

      {["submitted", "pending_review"].includes(status) ? (
        <div className="card card-pad">
          <h2 className="section-title">Review order</h2>
          <form onSubmit={(event) => review(event, "approve")} className="mt-3 space-y-2">
            <input name="reason" className="input" placeholder="Approval note (optional)" />
            <Button type="submit" busy={busy === "approve"}>Approve for scheduling</Button>
          </form>
          <form onSubmit={(event) => review(event, "reject")} className="mt-3 border-t pt-3">
            <input name="reason" className="input" placeholder="Rejection reason (required, 5+ chars)" required minLength={5} />
            <Button type="submit" busy={busy === "reject"} className="btn btn-danger mt-2">Reject order</Button>
          </form>
        </div>
      ) : null}

      {["awaiting_assignment", "assigned"].includes(status) ? (
        <div className="card card-pad">
          <h2 className="section-title">Assign a driver</h2>
          <form onSubmit={assign} className="mt-3 space-y-2">
            <select name="driver_id" className="input" required defaultValue="">
              <option value="" disabled>Choose an eligible driver</option>
              {drivers?.data.map((row) => (
                <option key={row.driver.id} value={row.driver.id}>
                  {row.driver.full_name} · {row.duty_label}{row.is_live ? " · live" : " · not live"}{row.active_batch ? " · has batch" : ""}
                </option>
              ))}
            </select>
            <input name="reason" className="input" placeholder="Assignment note (optional)" />
            <Button type="submit" busy={busy === "assign"}>Assign order</Button>
            <p className="text-xs text-muted">Eligibility, capacity, service area and duty are revalidated by the server.</p>
          </form>
          <div className="mt-3 border-t pt-3">
            <Button busy={busy === "scan"} className="btn btn-secondary" onClick={() => run("scan", "/manager/matching/scan", { order_ids: [orderId] }, "Matching scan complete. Review suggestions below.")}>
              {busy === "scan" ? <Loader2 size={15} className="animate-spin" aria-hidden /> : null}
              Scan active routes for this order
            </Button>
          </div>
        </div>
      ) : null}

      {suggestions.length ? (
        <div className="card card-pad">
          <h2 className="section-title">On-route suggestions</h2>
          <div className="mt-3 space-y-3">
            {suggestions.map((suggestion) => (
              <div key={suggestion.id} className="rounded-control border p-3">
                <p className="text-sm font-semibold">{suggestion.driver?.full_name}</p>
                <p className="text-xs text-muted">Detour {suggestion.detour_km?.toFixed(2)} km · score {suggestion.score?.toFixed(1) ?? "—"}</p>
                <p className="mt-1 text-[11px] leading-5 text-muted">{suggestion.reasons.map((reason) => reason.label).join(" · ")}</p>
                <div className="mt-2 flex gap-2">
                  <button className="btn btn-primary btn-sm" disabled={busy === `s-${suggestion.id}`} onClick={() => run(`s-${suggestion.id}`, `/manager/matching/suggestions/${suggestion.id}/approve`, {}, "Suggestion approved and order assigned.")}>Approve</button>
                  <button className="btn btn-secondary btn-sm" onClick={() => {
                    const reason = window.prompt("Reason for rejecting this suggestion (5+ characters)");
                    if (reason) void run(`r-${suggestion.id}`, `/manager/matching/suggestions/${suggestion.id}/reject`, { reason }, "Suggestion rejected.");
                  }}>Reject</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
