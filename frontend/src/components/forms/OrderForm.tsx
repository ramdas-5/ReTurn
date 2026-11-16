"use client";

import { CheckCircle2, Loader2, Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { ApiError, apiGet, apiUpload } from "@/lib/api";
import { Field } from "@/components/ui";
import type { OrderDetail } from "@/lib/types";

function defaultWindow(): string {
  const date = new Date(Date.now() + 24 * 60 * 60 * 1000);
  date.setMinutes(0, 0, 0);
  const offset = date.getTimezoneOffset();
  return new Date(date.getTime() - offset * 60000).toISOString().slice(0, 16);
}

export default function OrderForm({ serviceType }: { serviceType: "parcel" | "return" }) {
  const router = useRouter();
  const initial = useMemo(defaultWindow, []);
  const [photo, setPhoto] = useState<File | null>(null);
  const [exception, setException] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [availability, setAvailability] = useState<{
    availability_label: string;
    serviceable: boolean;
    reasons: string[];
  } | null>(null);
  const [checking, setChecking] = useState(false);

  function values(form: HTMLFormElement) {
    return Object.fromEntries(new FormData(form).entries()) as Record<string, string>;
  }

  async function checkAvailability(form: HTMLFormElement) {
    const data = values(form);
    setChecking(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        pickup_area: data.pickup_area,
        pickup_latitude: data.pickup_latitude,
        pickup_longitude: data.pickup_longitude,
        delivery_area: data.delivery_area,
        delivery_latitude: data.delivery_latitude,
        delivery_longitude: data.delivery_longitude,
        window_start: new Date(data.window_start).toISOString(),
        window_end: new Date(data.window_end).toISOString(),
      });
      const info = await apiGet<{
        availability_label: string;
        serviceable: boolean;
        reasons: string[];
      }>(`/availability?${params.toString()}`);
      setAvailability(info);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Availability check failed.");
    } finally {
      setChecking(false);
    }
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const form = event.currentTarget;
    const data = values(form);
    try {
      const payload = {
        service_type: serviceType,
        pickup: {
          contact_name: data.pickup_contact_name,
          contact_phone: data.pickup_contact_phone,
          address_line: data.pickup_address_line,
          area: data.pickup_area,
          city: data.pickup_city,
          state: data.pickup_state,
          latitude: Number(data.pickup_latitude),
          longitude: Number(data.pickup_longitude),
          instructions: data.pickup_instructions,
        },
        delivery: {
          contact_name: data.delivery_contact_name,
          contact_phone: data.delivery_contact_phone,
          address_line: data.delivery_address_line,
          area: data.delivery_area,
          city: data.delivery_city,
          state: data.delivery_state,
          latitude: Number(data.delivery_latitude),
          longitude: Number(data.delivery_longitude),
          instructions: data.delivery_instructions,
        },
        parcel: {
          name: data.parcel_name,
          description: data.parcel_description,
          category: data.parcel_category || "general",
          quantity: Number(data.quantity || 1),
          weight_kg: Number(data.weight_kg),
          length_cm: Number(data.length_cm),
          width_cm: Number(data.width_cm),
          height_cm: Number(data.height_cm),
          is_fragile: data.is_fragile === "on",
          ...(exception.trim() ? { photo_exception_reason: exception.trim() } : {}),
        },
        pickup_window_start: new Date(data.window_start).toISOString(),
        pickup_window_end: new Date(data.window_end).toISOString(),
        delivery_deadline: new Date(data.deadline).toISOString(),
        service_notes: data.service_notes,
        ...(serviceType === "return"
          ? {
              return_details: {
                product_name: data.product_name || data.parcel_name,
                original_order_reference: data.original_order_reference,
                reason: data.return_reason,
                return_authorization_reference: data.return_authorization_reference,
                merchant_name: data.merchant_name,
                destination_type: data.destination_type,
                authorization_confirmed: data.authorization_confirmed === "on",
                merchant_approval_required: data.merchant_approval_required === "on",
              },
            }
          : {}),
      };
      const formData = new FormData();
      formData.append("payload", JSON.stringify(payload));
      if (photo) formData.append("photo", photo);
      const order = await apiUpload<OrderDetail>("/orders", formData);
      router.push(`/consumer/orders/${order.id}/confirmation`);
    } catch (caught) {
      if (caught instanceof ApiError) {
        const fields = Object.values(caught.fields);
        setError(fields.length ? fields.join(" ") : caught.message);
      } else {
        setError("The order could not be submitted.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      {error ? (
        <p className="rounded-control border border-[#f3d1cb] bg-red-soft px-3 py-2 text-sm text-[#8c2f2f]" role="alert">
          {error}
        </p>
      ) : null}

      <section className="card card-pad">
        <h2 className="section-title">{serviceType === "return" ? "Return details" : "Pickup details"}</h2>
        <div className="field-grid mt-4">
          <Field label="Pickup contact name"><input name="pickup_contact_name" className="input" required /></Field>
          <Field label="Pickup phone"><input name="pickup_contact_phone" className="input" required minLength={6} /></Field>
          <Field label="Pickup address" className="sm:col-span-2"><input name="pickup_address_line" className="input" required /></Field>
          <Field label="Pickup area"><input name="pickup_area" className="input" required placeholder="e.g. Barasat" /></Field>
          <Field label="City"><input name="pickup_city" className="input" defaultValue="Kolkata" /></Field>
          <Field label="Pickup latitude"><input name="pickup_latitude" type="number" step="0.000001" className="input" defaultValue="22.724" required /></Field>
          <Field label="Pickup longitude"><input name="pickup_longitude" type="number" step="0.000001" className="input" defaultValue="88.478" required /></Field>
          <Field label="Pickup instructions" className="sm:col-span-2"><input name="pickup_instructions" className="input" placeholder="Gate code, landmark, etc." /></Field>
        </div>
      </section>

      {serviceType === "return" ? (
        <section className="card card-pad">
          <h2 className="section-title">Authorised return destination</h2>
          <div className="field-grid mt-4">
            <Field label="Product name"><input name="product_name" className="input" required /></Field>
            <Field label="Original order reference"><input name="original_order_reference" className="input" /></Field>
            <Field label="Return reason" className="sm:col-span-2"><input name="return_reason" className="input" required minLength={5} /></Field>
            <Field label="Merchant / business name"><input name="merchant_name" className="input" /></Field>
            <Field label="Return authorisation reference"><input name="return_authorization_reference" className="input" /></Field>
            <Field label="Destination type">
              <select name="destination_type" className="input" defaultValue="business">
                <option value="business">Business</option>
                <option value="warehouse">Warehouse</option>
                <option value="return_center">Return processing centre</option>
                <option value="hub">Authorised hub</option>
              </select>
            </Field>
            <div className="flex flex-col justify-end gap-2 text-sm">
              <label className="flex items-center gap-2"><input type="checkbox" name="authorization_confirmed" /> Customer authorised this return</label>
              <label className="flex items-center gap-2"><input type="checkbox" name="merchant_approval_required" /> Merchant approval required</label>
            </div>
          </div>
        </section>
      ) : null}

      <section className="card card-pad">
        <h2 className="section-title">Recipient</h2>
        <div className="field-grid mt-4">
          <Field label="Recipient name"><input name="delivery_contact_name" className="input" required /></Field>
          <Field label="Recipient phone"><input name="delivery_contact_phone" className="input" required minLength={6} /></Field>
          <Field label="Delivery address" className="sm:col-span-2"><input name="delivery_address_line" className="input" required /></Field>
          <Field label="Delivery area"><input name="delivery_area" className="input" required placeholder="e.g. Salt Lake" /></Field>
          <Field label="City"><input name="delivery_city" className="input" defaultValue="Kolkata" /></Field>
          <Field label="Delivery latitude"><input name="delivery_latitude" type="number" step="0.000001" className="input" defaultValue="22.58" required /></Field>
          <Field label="Delivery longitude"><input name="delivery_longitude" type="number" step="0.000001" className="input" defaultValue="88.41" required /></Field>
          <Field label="Delivery instructions" className="sm:col-span-2"><input name="delivery_instructions" className="input" /></Field>
        </div>
      </section>

      <section className="card card-pad">
        <h2 className="section-title">Parcel</h2>
        <div className="field-grid mt-4">
          <Field label="Parcel name"><input name="parcel_name" className="input" required /></Field>
          <Field label="Category">
            <select name="parcel_category" className="input" defaultValue="general">
              <option value="general">General</option>
              <option value="documents">Documents</option>
              <option value="clothing">Clothing</option>
              <option value="electronics">Electronics</option>
              <option value="fragile">Fragile</option>
              <option value="other">Other</option>
            </select>
          </Field>
          <Field label="Quantity"><input name="quantity" type="number" min={1} className="input" defaultValue={1} /></Field>
          <Field label="Weight (kg)"><input name="weight_kg" type="number" step="0.01" min={0.05} className="input" required /></Field>
          <Field label="Length (cm)"><input name="length_cm" type="number" step="0.1" className="input" required /></Field>
          <Field label="Width (cm)"><input name="width_cm" type="number" step="0.1" className="input" required /></Field>
          <Field label="Height (cm)"><input name="height_cm" type="number" step="0.1" className="input" required /></Field>
          <Field label="Description" className="sm:col-span-2"><textarea name="parcel_description" className="input" rows={2} /></Field>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="is_fragile" /> Fragile handling required</label>
        </div>
      </section>

      <section className="card card-pad">
        <h2 className="section-title">Schedule & photo</h2>
        <div className="field-grid mt-4">
          <Field label="Pickup window starts"><input name="window_start" type="datetime-local" className="input" defaultValue={initial} required /></Field>
          <Field label="Pickup window ends"><input name="window_end" type="datetime-local" className="input" defaultValue={initial.replace(/T\d{2}/, "T20")} required /></Field>
          <Field label="Delivery deadline" className="sm:col-span-2"><input name="deadline" type="datetime-local" className="input" defaultValue={initial.replace(/T\d{2}/, "T21")} required /></Field>
          <Field label="Service notes" className="sm:col-span-2"><textarea name="service_notes" className="input" rows={2} /></Field>
        </div>
        <div className="mt-4 rounded-control border bg-surface-muted p-4">
          <label className="label" htmlFor="photo">Exterior parcel photograph</label>
          <input
            id="photo"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="block w-full text-sm"
            onChange={(event) => setPhoto(event.target.files?.[0] ?? null)}
          />
          <p className="help">Photograph the outside packaging only. Never open sealed contents.</p>
          {!photo ? (
            <div className="mt-3">
              <label className="label" htmlFor="exception">Camera unavailable? Record an exception reason</label>
              <input id="exception" className="input" value={exception} onChange={(event) => setException(event.target.value)} placeholder="At least 12 characters" />
            </div>
          ) : (
            <p className="mt-2 inline-flex items-center gap-1.5 text-xs text-accent"><Upload size={13} aria-hidden /> {photo.name}</p>
          )}
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            className="btn btn-secondary"
            disabled={checking}
            onClick={(event) => checkAvailability(event.currentTarget.form as HTMLFormElement)}
          >
            {checking ? <Loader2 size={15} className="animate-spin" aria-hidden /> : null}
            Check service availability
          </button>
          {availability ? (
            <span className={`chip ${availability.serviceable ? "chip-teal" : "chip-red"}`}>
              <CheckCircle2 size={13} aria-hidden /> {availability.availability_label}
            </span>
          ) : null}
        </div>
        {availability?.reasons?.length ? (
          <p className="mt-2 text-xs text-muted">Reasons: {availability.reasons.join(", ")}</p>
        ) : null}
      </section>

      <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? <Loader2 size={16} className="animate-spin" aria-hidden /> : null}
          Submit {serviceType === "return" ? "return request" : "parcel order"}
        </button>
      </div>
    </form>
  );
}
