"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiError, apiPost, apiUpload } from "@/lib/api";

export default function ConsumerOrderPanel({ orderId, status }: { orderId: number; status: string }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const canEdit = !["picked_up", "in_transit", "out_for_delivery", "delivery_proof_pending", "delivered", "returned", "cancelled", "failed"].includes(status);

  async function upload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const file = (event.currentTarget.elements.namedItem("photo") as HTMLInputElement).files?.[0];
    if (!file) return setError("Choose a parcel photograph first.");
    setBusy("photo");
    setError(null);
    const form = new FormData();
    form.append("photo", file);
    form.append("is_primary", "true");
    try {
      await apiUpload(`/orders/${orderId}/images`, form);
      setMessage("Photograph added.");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Upload failed.");
    } finally {
      setBusy(null);
    }
  }

  async function cancel(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const reason = String(new FormData(event.currentTarget).get("reason") ?? "");
    setBusy("cancel");
    setError(null);
    try {
      await apiPost(`/orders/${orderId}/cancel`, { reason });
      setMessage("Order cancelled.");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Cancellation failed.");
    } finally {
      setBusy(null);
    }
  }

  async function reportIssue(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy("issue");
    setError(null);
    try {
      await apiPost("/issues", {
        category: form.get("category"),
        severity: form.get("severity"),
        subject: form.get("subject"),
        description: form.get("description"),
        order_id: orderId,
      });
      setMessage("Issue reported. A manager will review it.");
      event.currentTarget.reset();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Issue could not be reported.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-4">
      {error ? <p className="rounded-control bg-red-soft px-3 py-2 text-sm text-red-ink" role="alert">{error}</p> : null}
      {message ? <p className="rounded-control bg-accent-soft px-3 py-2 text-sm text-accent-strong">{message}</p> : null}

      {canEdit ? (
        <form onSubmit={upload} className="card card-pad">
          <h2 className="section-title">Add a parcel photograph</h2>
          <p className="mt-1 text-sm text-muted">Exterior packaging only, before the parcel is collected.</p>
          <input name="photo" type="file" accept="image/jpeg,image/png,image/webp" className="mt-3 block w-full text-sm" required />
          <button className="btn btn-secondary mt-3" disabled={busy === "photo"}>
            {busy === "photo" ? <Loader2 size={15} className="animate-spin" aria-hidden /> : null}
            Upload photograph
          </button>
        </form>
      ) : null}

      <details className="card card-pad">
        <summary className="cursor-pointer text-sm font-semibold">Report an issue with this order</summary>
        <form onSubmit={reportIssue} className="mt-4 space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <select name="category" className="input" defaultValue="delivery">
              <option value="delivery">Delivery</option>
              <option value="parcel">Parcel</option>
              <option value="pickup">Pickup</option>
              <option value="account">Account</option>
              <option value="other">Other</option>
            </select>
            <select name="severity" className="input" defaultValue="medium">
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </div>
          <input name="subject" className="input" placeholder="Short subject" required minLength={4} />
          <textarea name="description" className="input" rows={3} placeholder="What happened?" required minLength={10} />
          <button className="btn btn-secondary" disabled={busy === "issue"}>Submit issue</button>
        </form>
      </details>

      {canEdit ? (
        <details className="card card-pad">
          <summary className="cursor-pointer text-sm font-semibold text-danger">Cancel this order</summary>
          <form onSubmit={cancel} className="mt-4 space-y-3">
            <input name="reason" className="input" placeholder="Reason for cancellation (5+ characters)" required minLength={5} />
            <button className="btn btn-danger" disabled={busy === "cancel"}>Cancel order</button>
            <p className="text-xs text-muted">Cancellation is refused once a driver has the parcel in custody.</p>
          </form>
        </details>
      ) : null}
    </div>
  );
}
