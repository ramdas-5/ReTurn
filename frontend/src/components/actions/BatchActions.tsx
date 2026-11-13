"use client";

import { Check, Loader2, Play, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import ActionDialog from "@/components/actions/ActionDialog";
import { Callout } from "@/components/ui";
import { ApiError, apiPost } from "@/lib/api";
import type { Batch, PartnerProfile } from "@/lib/types";

function ErrorLine({ message }: { message: string | null }) {
  if (!message) return null;
  return <p className="text-xs text-[#8c2f2f]" role="alert">{message}</p>;
}

export function PartnerBatchActions({ batch }: { batch: Batch }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const offeredToMe = batch.status === "offered" && batch.eligibility?.offered_to_me;
  const canStart = batch.status === "accepted";

  async function accept() {
    setBusy(true);
    setError(null);
    try {
      await apiPost(`/batches/${batch.id}/decision`, { decision: "accept" });
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not accept the batch.");
    } finally {
      setBusy(false);
    }
  }

  async function start() {
    setBusy(true);
    setError(null);
    try {
      await apiPost(`/batches/${batch.id}/start`, {});
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not start the route.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      {batch.eligibility && !batch.eligibility.eligible ? (
        <Callout tone="warning" title="Not eligible for this batch">
          {batch.eligibility.reason}
        </Callout>
      ) : null}
      <div className="flex flex-wrap gap-2">
        {offeredToMe ? (
          <button type="button" className="btn btn-primary" onClick={accept} disabled={busy || !batch.eligibility?.eligible}>
            {busy ? <Loader2 size={16} className="animate-spin" aria-hidden /> : <Check size={16} aria-hidden />}
            Accept batch
          </button>
        ) : null}
        {offeredToMe ? (
          <ActionDialog
            label="Decline"
            title={`Decline ${batch.code}?`}
            description="Declining releases the offer but keeps the requests reserved until an administrator re-offers or cancels the batch."
            confirmLabel="Decline offer"
            tone="danger"
            triggerClassName="btn btn-secondary"
            reasonRequired
            reasonLabel="Why are you declining?"
            onConfirm={async (reason) => {
              await apiPost(`/batches/${batch.id}/decision`, { decision: "decline", reason });
              router.refresh();
            }}
          />
        ) : null}
        {canStart ? (
          <button type="button" className="btn btn-primary" onClick={start} disabled={busy}>
            {busy ? <Loader2 size={16} className="animate-spin" aria-hidden /> : <Play size={16} aria-hidden />}
            Start route
          </button>
        ) : null}
      </div>
      <ErrorLine message={error} />
    </div>
  );
}

export function AdminBatchActions({
  batch,
  partners,
}: {
  batch: Batch;
  partners: PartnerProfile[];
}) {
  const router = useRouter();
  const [partnerId, setPartnerId] = useState<string>("");
  const [note, setNote] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const verified = partners.filter((partner) => partner.verification_status === "verified");
  const canOffer = ["proposed", "declined"].includes(batch.status);
  const canReassign = ["proposed", "offered", "accepted"].includes(batch.status);

  async function run(key: string, action: () => Promise<unknown>) {
    setBusy(key);
    setError(null);
    setMessage(null);
    try {
      await action();
      setMessage("Batch updated.");
      setPartnerId("");
      setNote("");
      setReason("");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The batch action failed.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-4">
      {error ? <Callout tone="danger">{error}</Callout> : null}
      {message ? <Callout tone="accent">{message}</Callout> : null}

      {canOffer ? (
        <div className="rounded-control border bg-surface-muted p-4">
          <h3 className="text-sm font-semibold">Offer to a verified partner</h3>
          <p className="mt-1 text-xs leading-5 text-muted">
            Eligibility is checked server-side against verification, availability, capacity, handling and service area.
          </p>
          <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
            <select
              className="input"
              aria-label="Partner to offer"
              value={partnerId}
              onChange={(event) => setPartnerId(event.target.value)}
            >
              <option value="">Choose a verified partner…</option>
              {verified.map((partner) => (
                <option key={partner.user_id} value={partner.user_id}>
                  {partner.name} · {partner.vehicle_type} · {partner.max_weight_kg} kg
                </option>
              ))}
            </select>
            <input
              className="input"
              placeholder="Optional dispatch note"
              aria-label="Dispatch note"
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
            <button
              type="button"
              className="btn btn-primary"
              disabled={!partnerId || busy === "offer"}
              onClick={() =>
                run("offer", () =>
                  apiPost(`/batches/${batch.id}/offer`, {
                    partner_id: Number(partnerId),
                    note: note || undefined,
                  }),
                )
              }
            >
              {busy === "offer" ? <Loader2 size={15} className="animate-spin" aria-hidden /> : null}
              Offer
            </button>
          </div>
        </div>
      ) : null}

      {canReassign ? (
        <details className="rounded-control border p-4">
          <summary className="cursor-pointer text-sm font-semibold">Reassign with an audited reason</summary>
          <div className="mt-3 grid gap-2">
            <select
              className="input"
              aria-label="New partner"
              value={partnerId}
              onChange={(event) => setPartnerId(event.target.value)}
            >
              <option value="">Choose a new verified partner…</option>
              {verified.map((partner) => (
                <option key={partner.user_id} value={partner.user_id}>
                  {partner.name} · {partner.vehicle_type}
                </option>
              ))}
            </select>
            <textarea
              className="input min-h-[72px]"
              placeholder="Why is this batch being reassigned? (audit trail)"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
            <button
              type="button"
              className="btn btn-secondary justify-self-start"
              disabled={!partnerId || reason.trim().length < 5 || busy === "reassign"}
              onClick={() =>
                run("reassign", () =>
                  apiPost(`/batches/${batch.id}/reassign`, {
                    partner_id: Number(partnerId),
                    reason,
                  }),
                )
              }
            >
              {busy === "reassign" ? <Loader2 size={15} className="animate-spin" aria-hidden /> : null}
              Reassign
            </button>
          </div>
        </details>
      ) : null}

      <div className="flex flex-wrap gap-2">
        {batch.status === "accepted" ? (
          <button
            type="button"
            className="btn btn-secondary"
            disabled={busy === "start"}
            onClick={() => run("start", () => apiPost(`/batches/${batch.id}/start`, {}))}
          >
            <Play size={15} aria-hidden /> Start route (admin support)
          </button>
        ) : null}
        {!["in_progress", "completed", "cancelled"].includes(batch.status) ? (
          <ActionDialog
            label="Cancel batch"
            title={`Cancel ${batch.code}?`}
            description="This releases every reserved request back to pending matching and notifies customers and the assigned partner. It is recorded in the audit trail."
            confirmLabel="Cancel batch"
            tone="danger"
            triggerClassName="btn btn-danger"
            reasonRequired
            reasonLabel="Cancellation reason"
            icon={<X size={15} aria-hidden />}
            onConfirm={async (why) => {
              await apiPost(`/batches/${batch.id}/cancel`, { reason: why });
              router.refresh();
            }}
          />
        ) : null}
      </div>
    </div>
  );
}
