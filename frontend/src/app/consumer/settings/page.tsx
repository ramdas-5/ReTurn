"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Button, ErrorText } from "@/components/ui-bits";
import { Card, Field, PageHeader } from "@/components/ui";
import { ApiError, apiGet, apiPatch, apiPost } from "@/lib/api";
import type { ApiUser } from "@/lib/types";

export default function ConsumerSettingsPage() {
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { data } = useQuery({
    queryKey: ["me"],
    queryFn: () => apiGet<{ user: ApiUser }>("/users/me"),
  });

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    const form = new FormData(event.currentTarget);
    try {
      await apiPatch("/users/me", {
        full_name: form.get("full_name"),
        phone: form.get("phone"),
        notify_email: form.get("notify_email") === "on",
        notify_in_app: form.get("notify_in_app") === "on",
      });
      setMessage("Profile updated.");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Profile could not be updated.");
    } finally {
      setBusy(false);
    }
  }

  async function changePassword(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    const form = new FormData(event.currentTarget);
    try {
      await apiPost("/auth/password", Object.fromEntries(form.entries()));
      setMessage("Password changed.");
      event.currentTarget.reset();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Password could not be changed.");
    } finally {
      setBusy(false);
    }
  }

  const user = data?.user;

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader eyebrow="Profile & settings" title="Account details" description="Keep your contact details current and choose how ReTurn notifies you." />
      {error ? <ErrorText>{error}</ErrorText> : null}
      {message ? <p className="mb-4 rounded-control bg-accent-soft px-3 py-2 text-sm text-accent-strong">{message}</p> : null}
      <form onSubmit={save} className="card card-pad space-y-4">
        <div className="field-grid">
          <Field label="Full name"><input name="full_name" className="input" defaultValue={user?.full_name ?? ""} required /></Field>
          <Field label="Phone"><input name="phone" className="input" defaultValue={user?.phone ?? ""} /></Field>
          <Field label="Email"><input className="input" value={user?.email ?? ""} disabled /></Field>
          <Field label="Account type"><input className="input" value={user?.consumer_profile?.account_type ?? "individual"} disabled /></Field>
        </div>
        <div className="flex flex-wrap gap-4 text-sm">
          <label className="flex items-center gap-2"><input type="checkbox" name="notify_email" defaultChecked={user?.notify_email ?? true} /> Email notifications</label>
          <label className="flex items-center gap-2"><input type="checkbox" name="notify_in_app" defaultChecked={user?.notify_in_app ?? true} /> In-app notifications</label>
        </div>
        <Button type="submit" busy={busy}>Save profile</Button>
      </form>
      <form onSubmit={changePassword} className="card card-pad mt-5 space-y-3">
        <h2 className="section-title">Change password</h2>
        <Field label="Current password"><input name="current_password" type="password" className="input" required /></Field>
        <Field label="New password"><input name="new_password" type="password" className="input" required minLength={8} /></Field>
        <Field label="Confirm new password"><input name="confirm_password" type="password" className="input" required minLength={8} /></Field>
        <Button type="submit" busy={busy} className="btn btn-secondary">Update password</Button>
      </form>
    </div>
  );
}
