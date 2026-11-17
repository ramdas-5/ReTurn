"use client";

import { useQuery } from "@tanstack/react-query";

import { ProofReview } from "@/components/ReviewActions";
import { PageHeader } from "@/components/ui";
import { apiGetList } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { ProofMediaRow } from "@/lib/types";

export default function AdminProofsPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["proofs", "admin"], queryFn: () => apiGetList<ProofMediaRow>("/admin/proofs?per_page=100") });
  return (
    <div>
      <PageHeader eyebrow="Delivery proof audit" title="Platform-wide evidence" description="Every pickup and delivery proof, with its reviewer trail. An administrator review cannot fabricate a delivery; it only records verification." />
      {isLoading ? <p className="text-sm text-muted">Loading proofs…</p> : null}
      {error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-red-ink">{(error as Error).message}</p> : null}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data?.data.map((proof) => (
          <article key={proof.id} className="card card-pad">
            <div className="flex items-start justify-between gap-2"><div><p className="font-semibold">{proof.order_number}</p><p className="text-xs capitalize text-muted">{proof.proof_type} · {proof.driver?.full_name ?? "Driver"}</p></div><span className={`chip ${proof.verification_status === "valid" ? "chip-green" : proof.verification_status === "rejected" ? "chip-red" : "chip-amber"}`}>{proof.verification_status.replaceAll("_", " ")}</span></div>
            {proof.image_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={proof.image_url} alt={`${proof.proof_type} proof`} className="mt-3 max-h-44 w-full rounded-control border object-contain" />
            ) : null}
            <p className="mt-2 text-xs text-muted">Captured {formatDateTime(proof.captured_at)} · {proof.location.accuracy_m ?? "—"} m accuracy</p>
            {proof.verified_by ? <p className="text-xs text-muted">Reviewed by {proof.verified_by.full_name}</p> : null}
            {proof.verification_status === "pending_verification" ? <ProofReview proofId={proof.id} scope="admin" /> : null}
          </article>
        ))}
      </div>
      {data && data.data.length === 0 ? <p className="text-sm text-muted">No proof captured yet.</p> : null}
    </div>
  );
}
