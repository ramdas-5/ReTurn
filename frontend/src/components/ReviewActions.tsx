"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError, apiPatch } from "@/lib/api";
import { ErrorText } from "@/components/ui-bits";

export function ProofReview({ proofId, scope }: { proofId: number; scope: "manager" | "admin" }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function verify(status: string) {
    setBusy(true);
    setError(null);
    try {
      await apiPatch(`/${scope}/proofs/${proofId}/verify`, {
        verification_status: status,
        note: status === "rejected" ? "Rejected during review." : "Verified during review.",
      });
      await queryClient.invalidateQueries({ queryKey: ["proofs", scope] });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Proof could not be updated.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-2">
      {error ? <ErrorText>{error}</ErrorText> : null}
      <div className="flex gap-2">
        <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => verify("valid")}>Mark valid</button>
        <button className="btn btn-danger btn-sm" disabled={busy} onClick={() => verify("rejected")}>Reject</button>
      </div>
    </div>
  );
}

export function IssueReview({ issueId }: { issueId: number }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function resolve() {
    const note = window.prompt("Resolution note (5+ characters)");
    if (!note) return;
    setBusy(true);
    setError(null);
    try {
      await apiPatch(`/issues/${issueId}`, { status: "resolved", resolution_note: note });
      await queryClient.invalidateQueries({ queryKey: ["issues"] });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Issue could not be resolved.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-2">
      {error ? <ErrorText>{error}</ErrorText> : null}
      <button className="btn btn-primary btn-sm" disabled={busy} onClick={resolve}>Resolve issue</button>
    </div>
  );
}

export function ExceptionReview({ exceptionId, scope }: { exceptionId: number; scope: "manager" | "admin" }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function resolve(status: string) {
    const note = window.prompt("Resolution note (5+ characters)");
    if (!note) return;
    setBusy(true);
    setError(null);
    try {
      await apiPatch(`/${scope}/exceptions/${exceptionId}`, { status, resolution_note: note });
      await queryClient.invalidateQueries({ queryKey: ["exceptions", scope] });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Exception could not be updated.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-2">
      {error ? <ErrorText>{error}</ErrorText> : null}
      <div className="flex gap-2">
        <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => resolve("resolved")}>Resolve</button>
        <button className="btn btn-secondary btn-sm" disabled={busy} onClick={() => resolve("rejected")}>Reject</button>
      </div>
    </div>
  );
}
