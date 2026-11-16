"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Camera, Loader2, MapPin } from "lucide-react";
import { useState } from "react";

import { ApiError, apiPost, apiUpload } from "@/lib/api";
import { Button, ErrorText } from "@/components/ui-bits";

export default function DriverOrderActions({ orderId, status }: { orderId: number; status: string }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [coords, setCoords] = useState<{ lat: string; lng: string; accuracy: string }>({
    lat: "",
    lng: "",
    accuracy: "",
  });

  async function refresh(result: string) {
    setMessage(result);
    await queryClient.invalidateQueries({ queryKey: ["driver-assignment", String(orderId)] });
    await queryClient.invalidateQueries({ queryKey: ["driver-summary"] });
    await queryClient.invalidateQueries({ queryKey: ["driver-assignments"] });
  }

  async function simple(key: string, path: string) {
    setBusy(key);
    setError(null);
    setMessage(null);
    try {
      await apiPost(path);
      await refresh("Updated.");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Action failed.");
    } finally {
      setBusy(null);
    }
  }

  function locate() {
    if (!navigator.geolocation) {
      setError("This browser cannot provide a location. Enter coordinates manually or report a proof-capture issue.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setCoords({
          lat: position.coords.latitude.toFixed(6),
          lng: position.coords.longitude.toFixed(6),
          accuracy: String(Math.round(position.coords.accuracy)),
        });
      },
      () => setError("Location permission was denied. Enable it or enter coordinates manually."),
      { enableHighAccuracy: true, timeout: 15000 },
    );
  }

  async function capture(event: React.FormEvent<HTMLFormElement>, kind: "pickup" | "delivery") {
    event.preventDefault();
    const form = event.currentTarget;
    const file = (form.elements.namedItem("photo") as HTMLInputElement).files?.[0];
    if (!file) return setError("A freshly captured photo is required.");
    const data = new FormData(form);
    const payload = {
      latitude: Number(data.get("latitude")),
      longitude: Number(data.get("longitude")),
      accuracy_m: data.get("accuracy_m") ? Number(data.get("accuracy_m")) : undefined,
      captured_at: new Date().toISOString(),
      capture_source: "device_camera",
      recipient_name: data.get("recipient_name") || undefined,
      notes: data.get("notes") || undefined,
    };
    const body = new FormData();
    body.append("payload", JSON.stringify(payload));
    body.append("photo", file);
    setBusy(kind);
    setError(null);
    setMessage(null);
    try {
      await apiUpload(`/driver/orders/${orderId}/${kind === "pickup" ? "pickup" : "delivery-proof"}`, body);
      await refresh(kind === "pickup" ? "Pickup confirmed with proof." : "Delivery completed with proof.");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Proof capture failed.");
    } finally {
      setBusy(null);
    }
  }

  async function exception(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    setBusy("exception");
    setError(null);
    setMessage(null);
    try {
      await apiPost(`/driver/orders/${orderId}/exception`, data);
      await refresh("Issue reported to the operations team.");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Issue could not be reported.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-4">
      {error ? <ErrorText>{error}</ErrorText> : null}
      {message ? <p className="rounded-control bg-accent-soft px-3 py-2 text-sm text-accent-strong">{message}</p> : null}

      <div className="card card-pad">
        <h2 className="section-title">Next action</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {["assigned", "pickup_scheduled"].includes(status) ? (
            <>
              <Button busy={busy === "accept"} onClick={() => simple("accept", `/driver/orders/${orderId}/accept`)}>Accept assignment</Button>
              <Button busy={busy === "arrived"} className="btn btn-secondary" onClick={() => simple("arrived", `/driver/orders/${orderId}/arrived-pickup`)}>Mark arrived at pickup</Button>
            </>
          ) : null}
          {status === "picked_up" ? (
            <Button busy={busy === "depart"} onClick={() => simple("depart", `/driver/orders/${orderId}/depart`)}>Depart pickup</Button>
          ) : null}
          {status === "in_transit" ? (
            <Button busy={busy === "out"} onClick={() => simple("out", `/driver/orders/${orderId}/out-for-delivery`)}>Out for delivery</Button>
          ) : null}
          {status === "out_for_delivery" || status === "delivery_proof_pending" ? (
            <span className="chip chip-amber">Capture delivery proof below to complete</span>
          ) : null}
        </div>
        <p className="mt-3 text-xs leading-5 text-muted">
          Delivery cannot be marked complete without valid proof. If capture is impossible, report a proof-capture exception.
        </p>
      </div>

      {status === "pickup_arrived" ? (
        <form onSubmit={(event) => capture(event, "pickup")} className="card card-pad space-y-3">
          <h2 className="section-title">Confirm pickup</h2>
          <p className="text-sm text-muted">Capture the parcel before it leaves the sender. Location is required by policy when GPS validation is enabled.</p>
          <LocationFields coords={coords} locate={locate} setCoords={setCoords} />
          <label className="label" htmlFor="pickup-photo">Pickup photograph</label>
          <input id="pickup-photo" name="photo" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" className="block w-full text-sm" required />
          <input name="notes" className="input" placeholder="Optional notes" />
          <Button type="submit" busy={busy === "pickup"}><Camera size={15} aria-hidden /> Confirm pickup with proof</Button>
        </form>
      ) : null}

      {status === "out_for_delivery" || status === "delivery_proof_pending" ? (
        <form onSubmit={(event) => capture(event, "delivery")} className="card card-pad space-y-3">
          <h2 className="section-title">Delivery proof</h2>
          <p className="text-sm text-muted">A fresh photograph is required. GPS must be within the configured radius of the delivery stop.</p>
          <LocationFields coords={coords} locate={locate} setCoords={setCoords} />
          <label className="label" htmlFor="delivery-photo">Delivery photograph</label>
          <input id="delivery-photo" name="photo" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" className="block w-full text-sm" required />
          <div className="grid gap-3 sm:grid-cols-2">
            <input name="recipient_name" className="input" placeholder="Recipient name (optional)" />
            <input name="notes" className="input" placeholder="Notes (optional)" />
          </div>
          <Button type="submit" busy={busy === "delivery"}><Camera size={15} aria-hidden /> Complete delivery</Button>
        </form>
      ) : null}

      <details className="card card-pad">
        <summary className="cursor-pointer text-sm font-semibold text-danger">Report a delivery issue</summary>
        <form onSubmit={exception} className="mt-3 space-y-3">
          <select name="exception_type" className="input" defaultValue="recipient_unavailable">
            <option value="recipient_unavailable">Recipient unavailable</option>
            <option value="address_not_found">Address not found</option>
            <option value="parcel_damaged">Parcel damaged</option>
            <option value="access_issue">Access issue</option>
            <option value="proof_capture_failed">Proof capture failed</option>
            <option value="other">Other</option>
          </select>
          <textarea name="description" className="input" rows={3} placeholder="Describe the issue (10+ characters)" required minLength={10} />
          <Button type="submit" busy={busy === "exception"} className="btn btn-danger">Report issue</Button>
        </form>
      </details>
    </div>
  );
}

function LocationFields({
  coords,
  locate,
  setCoords,
}: {
  coords: { lat: string; lng: string; accuracy: string };
  locate: () => void;
  setCoords: (value: { lat: string; lng: string; accuracy: string }) => void;
}) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <span className="label !mb-0">Capture location</span>
        <button type="button" className="btn btn-secondary btn-sm" onClick={locate}><MapPin size={14} aria-hidden /> Use my location</button>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <input name="latitude" type="number" step="0.000001" className="input" placeholder="Latitude" value={coords.lat} onChange={(event) => setCoords({ ...coords, lat: event.target.value })} required />
        <input name="longitude" type="number" step="0.000001" className="input" placeholder="Longitude" value={coords.lng} onChange={(event) => setCoords({ ...coords, lng: event.target.value })} required />
        <input name="accuracy_m" type="number" step="1" className="input" placeholder="Accuracy (m)" value={coords.accuracy} onChange={(event) => setCoords({ ...coords, accuracy: event.target.value })} />
      </div>
      <p className="help">Coordinates are only sent with this proof. ReTurn does not invent a location.</p>
    </div>
  );
}
