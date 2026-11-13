"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import ActionDialog from "@/components/actions/ActionDialog";
import { ApiError, apiPost } from "@/lib/api";
import { nextParcelEvent, parcelActionLabel } from "@/lib/format";
import type { ParcelStatus } from "@/lib/types";

export default function ParcelActions({
  parcelId,
  status,
  code,
  disabled = false,
}: {
  parcelId: number;
  status: ParcelStatus;
  code: string;
  disabled?: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const next = nextParcelEvent(status);
  const label = parcelActionLabel(status);
  const notes =
    next === "pickup_arrived"
      ? `Arrived at the pickup for ${code}.`
      : next === "picked_up"
        ? "Parcel collected from the customer."
        : next === "in_transit"
          ? "Parcel loaded and moving to the next stop."
          : "Handover completed and confirmed.";

  async function advance() {
    if (!next) return;
    setBusy(true);
    setError(null);
    try {
      await apiPost(`/parcels/${parcelId}/events`, { event_type: next, notes });
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Status update failed.");
    } finally {
      setBusy(false);
    }
  }

  if (status === "delivered" || status === "failed" || status === "pending") {
    return (
      <span className="text-xs text-muted">
        {status === "delivered" ? "Completed" : status === "failed" ? "Needs review" : "Awaiting acceptance"}
      </span>
    );
  }

  return (
    <div className="flex flex-col items-start gap-2">
      <div className="flex flex-wrap gap-2">
        {next ? (
          <button type="button" className="btn btn-primary btn-sm" onClick={advance} disabled={busy || disabled}>
            {busy ? <Loader2 size={14} className="animate-spin" aria-hidden /> : null}
            {label}
          </button>
        ) : null}
        <ActionDialog
          label="Problem"
          title={`Report a problem with ${code}`}
          description="This marks the parcel failed, opens an issue for the dispatch team and notifies the customer. It does not erase the tracking history."
          confirmLabel="Mark parcel failed"
          tone="danger"
          triggerClassName="btn btn-secondary btn-sm"
          reasonRequired
          reasonLabel="What went wrong?"
          disabled={disabled}
          onConfirm={async (reason) => {
            await apiPost(`/parcels/${parcelId}/events`, { event_type: "failed", notes: reason });
            router.refresh();
          }}
        />
      </div>
      {error ? <p className="text-xs text-[#8c2f2f]">{error}</p> : null}
    </div>
  );
}
