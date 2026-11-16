"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button, ErrorText } from "@/components/ui-bits";
import { Card, Field, PageHeader } from "@/components/ui";
import { ApiError, apiGet, apiPut } from "@/lib/api";
import type { BusinessProfile } from "@/lib/types";

type Payload = { business_profile: BusinessProfile | null; account_type: string };

export default function BusinessProfilePage() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { data, isLoading } = useQuery({
    queryKey: ["business-profile"],
    queryFn: () => apiGet<Payload>("/business-profiles/me"),
  });

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const form = new FormData(event.currentTarget);
    const payload = Object.fromEntries(form.entries());
    try {
      await apiPut("/business-profiles/me", {
        ...payload,
        latitude: payload.latitude ? Number(payload.latitude) : undefined,
        longitude: payload.longitude ? Number(payload.longitude) : undefined,
      });
      await queryClient.invalidateQueries({ queryKey: ["business-profile"] });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Business profile could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  const profile = data?.business_profile;

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        eyebrow="Business account"
        title="Business profile"
        description="A business profile lets you create orders as a company and keep a reference for your own operations."
        actions={profile ? <span className={`chip ${profile.verification_status === "verified" ? "chip-green" : "chip-amber"}`}>{profile.verification_status}</span> : null}
      />
      {isLoading ? <p className="text-sm text-muted">Loading profile…</p> : null}
      {profile ? (
        <Card className="mb-5">
          <h2 className="section-title">{profile.business_name}</h2>
          <p className="mt-1 text-sm text-muted">{profile.category ?? "Category not set"} · {profile.area ?? "Area not set"}</p>
          <p className="mt-2 text-[13px]">{profile.contact_email} · {profile.contact_phone}</p>
        </Card>
      ) : null}
      <form onSubmit={submit} className="card card-pad space-y-4">
        {error ? <ErrorText>{error}</ErrorText> : null}
        <div className="field-grid">
          <Field label="Business name"><input name="business_name" className="input" defaultValue={profile?.business_name ?? ""} required /></Field>
          <Field label="Category"><input name="category" className="input" defaultValue={profile?.category ?? ""} /></Field>
          <Field label="Contact phone"><input name="contact_phone" className="input" defaultValue={profile?.contact_phone ?? ""} /></Field>
          <Field label="Contact email"><input name="contact_email" type="email" className="input" defaultValue={profile?.contact_email ?? ""} /></Field>
          <Field label="Address" className="sm:col-span-2"><input name="address_line" className="input" defaultValue={profile?.address_line ?? ""} /></Field>
          <Field label="Area"><input name="area" className="input" defaultValue={profile?.area ?? ""} /></Field>
          <Field label="City"><input name="city" className="input" defaultValue={profile?.city ?? "Kolkata"} /></Field>
          <Field label="State"><input name="state" className="input" defaultValue={profile?.state ?? "West Bengal"} /></Field>
          <Field label="Postal code"><input name="postal_code" className="input" defaultValue={profile?.postal_code ?? ""} /></Field>
          <Field label="Tax ID"><input name="tax_id" className="input" defaultValue={profile?.tax_id ?? ""} /></Field>
          <Field label="Registration number"><input name="registration_number" className="input" defaultValue={profile?.registration_number ?? ""} /></Field>
          <Field label="Latitude"><input name="latitude" type="number" step="0.000001" className="input" defaultValue={profile?.location?.latitude ?? ""} /></Field>
          <Field label="Longitude"><input name="longitude" type="number" step="0.000001" className="input" defaultValue={profile?.location?.longitude ?? ""} /></Field>
        </div>
        <Button type="submit" busy={busy}>Save business profile</Button>
      </form>
    </div>
  );
}
