"use client";

import { useQuery } from "@tanstack/react-query";

import { ProofReview } from "@/components/ReviewActions";
import { PageHeader } from "@/components/ui";
import { apiGetList } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { ProofMediaRow } from "@/lib/types";

export default function ManagerProofsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["proofs", "manager"],
    queryFn: () => apiGetList<ProofMediaRow>("/manager/proofs?per_page=50"),
  });

  return (
    <div>
      <PageHeader eyebrow="Proof verification" title="Pickup and delivery evidence" description="Review captured proof from orders in your service areas. Verification never rewrites history: it records who reviewed what." />
      {isLoading ? <p className="text-sm text-muted">Loading proofs…</p> : null}
      {error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-[#8c2f2f]">{(error as Error).message}</p> : null}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data?.data.map((proof) => (
          <article key={proof.id} className="card card-pad">
            <div className="flex items-start justify-between gap-2">
              <div><p className="font-semibold">{proof.order_number}</p><p className="text-xs capitalize text-muted">{proof.proof_type} proof · {proof.driver?.full_name ?? "Driver"}</p></div>
              <span className={`chip ${proof.verification_status === "valid" ? "chip-green" : proof.verification_status === "rejected" ? "chip-red" : "chip-amber"}`}>{proof.verification_status.replaceAll("_", " ")}</span>
            </div>
            {proof.image_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={proof.image_url} alt={`${proof.proof_type} proof for ${proof.order_number}`} className="mt-3 max-h-44 w-full rounded-control border object-contain" />
            ) : <p className="mt-3 text-sm text-muted">No image available.</p>}
            <p className="mt-2 text-xs text-muted">Captured {formatDateTime(proof.captured_at)} · received {formatDateTime(proof.received_at)}</p>
            <p className="mt-1 text-xs text-muted">Location accuracy {proof.location.accuracy_m ?? "—"} m · distance from stop {proof.location.distance_from_stop_m ?? "—"} m</p>
            {proof.verification_status === "pending_verification" ? <ProofReview proofId={proof.id} scope="manager" /> : null}
          </article>
        ))}
      </div>
      {data && data.data.length === 0 ? <p className="text-sm text-muted">No proof has been captured for your orders yet.</p> : null}
    </div>
  );
}
