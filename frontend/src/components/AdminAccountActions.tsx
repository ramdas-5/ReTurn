"use client";

import { useState } from "react";

import { ApiError, apiPatch } from "@/lib/api";
import { ErrorText } from "@/components/ui-bits";

export function AccountStatusActions({ userId, status }: { userId: number; status: string }) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const next = status === "active" ? "suspended" : "active";

  async function change() {
    const reason = window.prompt(`Reason for setting this account to ${next} (5+ characters)`);
    if (!reason) return;
    setBusy(true);
    setError(null);
    try {
      await apiPatch(`/users/${userId}/status`, { status: next, reason });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Account status could not be changed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      {error ? <ErrorText>{error}</ErrorText> : null}
      <button className={`btn btn-sm ${status === "active" ? "btn-danger" : "btn-secondary"}`} disabled={busy} onClick={change}>
        {status === "active" ? "Suspend" : "Activate"}
      </button>
    </div>
  );
}

export function DriverVerificationActions({ userId }: { userId: number }) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function verify(status: string) {
    const note = window.prompt("Verification note (optional)") ?? "";
    setBusy(true);
    setError(null);
    try {
      await apiPatch(`/users/${userId}/driver-verification`, { verification_status: status, note });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Driver could not be updated.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-2">
      {error ? <ErrorText>{error}</ErrorText> : null}
      <div className="flex gap-2">
        <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => verify("verified")}>Verify driver</button>
        <button className="btn btn-secondary btn-sm" disabled={busy} onClick={() => verify("rejected")}>Reject</button>
      </div>
    </div>
  );
}

export function VehicleVerificationActions({ vehicleId }: { vehicleId: number }) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function update(status: string) {
    setBusy(true);
    setError(null);
    try {
      await apiPatch(`/admin/vehicles/${vehicleId}`, { verification_status: status, reason: "Administrator fleet review" });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Vehicle could not be updated.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-2">
      {error ? <ErrorText>{error}</ErrorText> : null}
      <div className="flex gap-2">
        <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => update("verified")}>Approve vehicle</button>
        <button className="btn btn-secondary btn-sm" disabled={busy} onClick={() => update("rejected")}>Reject</button>
      </div>
    </div>
  );
}
