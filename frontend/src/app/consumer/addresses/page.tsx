"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useState } from "react";

import { Button, ErrorText } from "@/components/ui-bits";
import { Card, Field, PageHeader } from "@/components/ui";
import { ApiError, apiDelete, apiGetList, apiPost } from "@/lib/api";
import type { SavedAddress } from "@/lib/types";

export default function AddressesPage() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { data, isLoading } = useQuery({
    queryKey: ["addresses"],
    queryFn: () => apiGetList<SavedAddress>("/users/me/addresses"),
  });

  async function add(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const form = new FormData(event.currentTarget);
    const values = Object.fromEntries(form.entries());
    try {
      await apiPost("/users/me/addresses", {
        ...values,
        latitude: Number(values.latitude),
        longitude: Number(values.longitude),
        is_default_pickup: values.is_default_pickup === "on",
      });
      await queryClient.invalidateQueries({ queryKey: ["addresses"] });
      event.currentTarget.reset();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Address could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    try {
      await apiDelete(`/users/me/addresses/${id}`);
      await queryClient.invalidateQueries({ queryKey: ["addresses"] });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Address could not be removed.");
    }
  }

  return (
    <div>
      <PageHeader eyebrow="Saved addresses" title="Your reusable locations" description="Saved addresses speed up pickup and delivery entry. They are private to your account." />
      <div className="grid gap-6 lg:grid-cols-[1.1fr_1fr]">
        <div className="space-y-3">
          {isLoading ? <p className="text-sm text-muted">Loading addresses…</p> : null}
          {data?.data.map((address) => (
            <Card key={address.id} className="flex items-start justify-between gap-3">
              <div>
                <p className="font-semibold">{address.label} {address.is_default_pickup ? <span className="chip chip-teal ml-2">default pickup</span> : null}</p>
                <p className="mt-1 text-sm text-muted">{address.address_line}, {address.area}, {address.city}</p>
                <p className="mt-1 text-xs text-muted">{address.contact_name} · {address.contact_phone}</p>
              </div>
              <button onClick={() => remove(address.id)} className="btn btn-ghost btn-sm text-danger" aria-label={`Delete ${address.label}`}><Trash2 size={15} aria-hidden /></button>
            </Card>
          ))}
          {data && data.data.length === 0 ? <p className="text-sm text-muted">No saved addresses yet.</p> : null}
        </div>
        <form onSubmit={add} className="card card-pad space-y-3 self-start">
          <h2 className="section-title">Add an address</h2>
          {error ? <ErrorText>{error}</ErrorText> : null}
          <Field label="Label"><input name="label" className="input" placeholder="Home, office, warehouse" required /></Field>
          <Field label="Contact name"><input name="contact_name" className="input" required /></Field>
          <Field label="Contact phone"><input name="contact_phone" className="input" required /></Field>
          <Field label="Address"><input name="address_line" className="input" required /></Field>
          <Field label="Area"><input name="area" className="input" required /></Field>
          <Field label="City"><input name="city" className="input" defaultValue="Kolkata" /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Latitude"><input name="latitude" type="number" step="0.000001" className="input" required /></Field>
            <Field label="Longitude"><input name="longitude" type="number" step="0.000001" className="input" required /></Field>
          </div>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="is_default_pickup" /> Default pickup address</label>
          <Button type="submit" busy={busy}>Save address</Button>
        </form>
      </div>
    </div>
  );
}
