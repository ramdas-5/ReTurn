"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import ActionDialog from "@/components/actions/ActionDialog";
import { Callout } from "@/components/ui";
import { ApiError, apiPatch } from "@/lib/api";
import type { ApiUser, Issue, PartnerProfile } from "@/lib/types";

export function CustomerAccountAction({ customer }: { customer: ApiUser }) {
  const router = useRouter();
  return (
    <ActionDialog
      label={customer.disabled ? "Re-enable account" : "Disable account"}
      title={`${customer.disabled ? "Re-enable" : "Disable"} ${customer.name}?`}
      description={
        customer.disabled
          ? "The customer will be able to sign in again immediately. Existing requests are unaffected."
          : "The customer's active sessions are revoked and sign-in is blocked. Requests and tracking history are preserved."
      }
      confirmLabel={customer.disabled ? "Re-enable" : "Disable"}
      tone={customer.disabled ? "secondary" : "danger"}
      triggerClassName="btn btn-secondary btn-sm"
      onConfirm={async () => {
        await apiPatch(`/customers/${customer.id}`, { disabled: !customer.disabled });
        router.refresh();
      }}
    />
  );
}

export function PartnerVerificationActions({ profile }: { profile: PartnerProfile }) {
  const router = useRouter();
  return (
    <div className="flex flex-wrap gap-2">
      {profile.verification_status !== "verified" ? (
        <ActionDialog
          label="Verify"
          title={`Verify ${profile.name}?`}
          description="Verification unlocks batch offers. Vehicle capacity, handling capability and service area still apply to every offer."
          confirmLabel="Verify partner"
          triggerClassName="btn btn-primary btn-sm"
          reasonLabel="Verification note (optional)"
          onConfirm={async (note) => {
            await apiPatch(`/partners/${profile.user_id}/verify`, { decision: "verified", note });
            router.refresh();
          }}
        />
      ) : null}
      {profile.verification_status !== "rejected" ? (
        <ActionDialog
          label="Reject"
          title={`Reject ${profile.name}?`}
          description="The partner will not receive offers. A reason is required and is shown to them in their profile."
          confirmLabel="Reject partner"
          tone="danger"
          triggerClassName="btn btn-secondary btn-sm"
          reasonRequired
          reasonLabel="What needs to change?"
          onConfirm={async (note) => {
            await apiPatch(`/partners/${profile.user_id}/verify`, { decision: "rejected", note });
            router.refresh();
          }}
        />
      ) : null}
      {profile.verification_status === "verified" ? (
        <ActionDialog
          label="Set pending"
          title="Move verification back to pending?"
          description="Use this if documents need re-checking. Existing accepted batches are not cancelled automatically."
          confirmLabel="Set pending"
          tone="secondary"
          triggerClassName="btn btn-ghost btn-sm"
          reasonLabel="Internal note (optional)"
          onConfirm={async (note) => {
            await apiPatch(`/partners/${profile.user_id}/verify`, { decision: "pending", note });
            router.refresh();
          }}
        />
      ) : null}
    </div>
  );
}

export function IssueResolutionForm({ issue }: { issue: Issue }) {
  const router = useRouter();
  const [status, setStatus] = useState(issue.status);
  const [note, setNote] = useState(issue.resolution_note ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await apiPatch(`/issues/${issue.id}`, { status, resolution_note: note || undefined });
      setMessage("Issue updated and audited.");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not update the issue.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      {error ? <p className="text-xs text-[#8c2f2f]">{error}</p> : null}
      {message ? <Callout tone="accent">{message}</Callout> : null}
      <div className="flex flex-wrap items-center gap-2">
        <select
          className="input !w-auto !py-1.5 text-xs"
          value={status}
          onChange={(event) => setStatus(event.target.value as Issue["status"])}
          aria-label="Issue status"
        >
          <option value="open">Open</option>
          <option value="in_review">In review</option>
          <option value="resolved">Resolved</option>
        </select>
        <input
          className="input !w-auto flex-1 !py-1.5 text-xs"
          placeholder="Resolution note"
          value={note}
          onChange={(event) => setNote(event.target.value)}
          aria-label="Resolution note"
        />
        <button type="button" className="btn btn-secondary btn-sm" onClick={submit} disabled={busy}>
          {busy ? <Loader2 size={13} className="animate-spin" aria-hidden /> : null}
          Save
        </button>
      </div>
    </div>
  );
}
