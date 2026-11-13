"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Callout, Field } from "@/components/ui";
import { ApiError, apiPatch } from "@/lib/api";
import type { ApiUser } from "@/lib/types";

export default function SettingsForm({ user }: { user: ApiUser }) {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [passwordBusy, setPasswordBusy] = useState(false);

  async function saveProfile(formData: FormData) {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await apiPatch("/auth/me", {
        name: String(formData.get("name") ?? ""),
        phone: String(formData.get("phone") ?? ""),
        timezone: String(formData.get("timezone") ?? "Asia/Kolkata"),
        notify_email: formData.get("notify_email") === "on",
        notify_in_app: formData.get("notify_in_app") === "on",
      });
      setMessage("Profile saved.");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not save your profile.");
    } finally {
      setBusy(false);
    }
  }

  async function changePassword(formData: FormData) {
    setPasswordBusy(true);
    setError(null);
    setMessage(null);
    try {
      await apiPatch("/auth/me", {
        current_password: String(formData.get("current_password") ?? ""),
        new_password: String(formData.get("new_password") ?? ""),
      });
      setMessage("Password updated. Other sessions stay valid until they expire.");
      (document.getElementById("password-form") as HTMLFormElement | null)?.reset();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not update your password.");
    } finally {
      setPasswordBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <form action={saveProfile} className="card card-pad space-y-4">
        <div>
          <h2 className="section-title">Profile</h2>
          <p className="mt-1 text-sm text-muted">Contact details used for operational updates.</p>
        </div>
        {message ? <Callout tone="accent">{message}</Callout> : null}
        {error ? <Callout tone="danger">{error}</Callout> : null}
        <Field label="Full name" htmlFor="settings-name">
          <input id="settings-name" name="name" className="input" defaultValue={user.name} required minLength={2} />
        </Field>
        <Field label="Email" htmlFor="settings-email" hint="Email changes require administrator support in this MVP.">
          <input id="settings-email" className="input" defaultValue={user.email} disabled />
        </Field>
        <Field label="Phone" htmlFor="settings-phone">
          <input id="settings-phone" name="phone" type="tel" className="input" defaultValue={user.phone ?? ""} />
        </Field>
        <Field label="Time zone" htmlFor="settings-timezone" hint="Schedules are stored in UTC and displayed in this zone.">
          <select id="settings-timezone" name="timezone" className="input" defaultValue={user.timezone}>
            <option value="Asia/Kolkata">Asia/Kolkata (IST)</option>
            <option value="UTC">UTC</option>
          </select>
        </Field>
        <fieldset className="space-y-2 rounded-control border bg-surface-muted p-4 text-sm">
          <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-muted">Notifications</legend>
          <label className="flex items-center gap-2">
            <input type="checkbox" name="notify_email" defaultChecked={user.notify_email ?? true} className="accent-[#087c60]" />
            Email updates
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" name="notify_in_app" defaultChecked={user.notify_in_app ?? true} className="accent-[#087c60]" />
            In-app notifications
          </label>
        </fieldset>
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? <Loader2 size={16} className="animate-spin" aria-hidden /> : null}
          Save profile
        </button>
      </form>

      <form id="password-form" action={changePassword} className="card card-pad space-y-4">
        <div>
          <h2 className="section-title">Password</h2>
          <p className="mt-1 text-sm text-muted">Passwords are hashed with Argon2id and never logged.</p>
        </div>
        <Field label="Current password" htmlFor="current-password">
          <input id="current-password" name="current_password" type="password" autoComplete="current-password" className="input" required />
        </Field>
        <Field label="New password" htmlFor="new-password" hint="At least 8 characters including a letter and a number.">
          <input id="new-password" name="new_password" type="password" autoComplete="new-password" className="input" required minLength={8} />
        </Field>
        <button type="submit" className="btn btn-secondary" disabled={passwordBusy}>
          {passwordBusy ? <Loader2 size={16} className="animate-spin" aria-hidden /> : null}
          Update password
        </button>
      </form>
    </div>
  );
}
