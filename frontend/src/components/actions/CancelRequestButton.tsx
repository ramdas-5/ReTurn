"use client";

import { useRouter } from "next/navigation";

import ActionDialog from "@/components/actions/ActionDialog";
import { apiPost } from "@/lib/api";

export default function CancelRequestButton({ requestId, code }: { requestId: number; code: string }) {
  const router = useRouter();
  return (
    <ActionDialog
      label="Cancel request"
      title={`Cancel ${code}?`}
      description="Cancellation is only allowed before a partner accepts the batch. If the request is in a proposed batch, the proposal is dissolved so other parcels are not blocked."
      confirmLabel="Cancel request"
      tone="danger"
      reasonRequired
      reasonLabel="Why are you cancelling?"
      onConfirm={async (reason) => {
        await apiPost(`/requests/${requestId}/cancel`, { reason });
        router.refresh();
      }}
    />
  );
}
