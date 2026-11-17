"use client";

import { Loader2, LockKeyhole } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiError, apiPost } from "@/lib/api";
import type { AuthMe } from "@/lib/types";

type Mode = "login" | "register";

export default function AuthForm({ nextPath }: { nextPath?: string }) {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [business, setBusiness] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    const values = Object.fromEntries(new FormData(event.currentTarget).entries());
    const payload: Record<string, unknown> = { ...values };
    if (mode === "register") {
      payload.account_type = business ? "business" : "individual";
      if (business) payload.business = { business_name: values.business_name };
      delete payload.business_name;
    }
    try {
      const me = await apiPost<AuthMe>(mode === "login" ? "/auth/login" : "/auth/register", payload);
      const target =
        nextPath && nextPath.startsWith("/") ? nextPath : `/${me.user.role}`;
      router.push(target);
      router.refresh();
    } catch (caught) {
      if (caught instanceof ApiError) {
        const fields = Object.values(caught.fields);
        setError(fields.length ? fields.join(" ") : caught.message);
      } else {
        setError("Something went wrong. Try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card card-pad">
      <div className="mb-6 flex rounded-control bg-surface-tint p-1" role="tablist" aria-label="Account access">
        {(["login", "register"] as const).map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={mode === value}
            onClick={() => {
              setMode(value);
              setError(null);
            }}
            className={`flex-1 rounded-[8px] px-3 py-2 text-sm font-medium transition ${
              mode === value ? "bg-surface text-ink shadow-sm" : "text-muted"
            }`}
          >
            {value === "login" ? "Sign in" : "Create account"}
          </button>
        ))}
      </div>

      <form onSubmit={submit} className="space-y-4" noValidate>
        {error ? (
          <p className="rounded-control border border-red-border bg-red-soft px-3 py-2 text-sm text-red-ink" role="alert">
            {error}
          </p>
        ) : null}

        {mode === "register" ? (
          <>
            <div>
              <label className="label" htmlFor="full_name">Full name</label>
              <input id="full_name" name="full_name" className="input" autoComplete="name" required minLength={2} />
            </div>
            <div>
              <label className="label" htmlFor="phone">Phone</label>
              <input id="phone" name="phone" className="input" autoComplete="tel" required minLength={6} />
            </div>
            <div>
              <span className="label">Account type</span>
              <div className="grid grid-cols-2 gap-2">
                <label className="flex cursor-pointer items-center gap-2 rounded-control border bg-surface px-3 py-2.5 text-sm">
                  <input type="radio" checked={!business} onChange={() => setBusiness(false)} /> Individual
                </label>
                <label className="flex cursor-pointer items-center gap-2 rounded-control border bg-surface px-3 py-2.5 text-sm">
                  <input type="radio" checked={business} onChange={() => setBusiness(true)} /> Business
                </label>
              </div>
              <p className="help">Only consumers can self-register. Driver, manager and admin accounts are provisioned by ReTurn.</p>
            </div>
            {business ? (
              <div>
                <label className="label" htmlFor="business_name">Business name</label>
                <input id="business_name" name="business_name" className="input" required />
              </div>
            ) : null}
          </>
        ) : null}

        <div>
          <label className="label" htmlFor="email">Email</label>
          <input id="email" name="email" type="email" className="input" autoComplete="email" required />
        </div>
        <div>
          <label className="label" htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            className="input"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            required
            minLength={mode === "register" ? 8 : 1}
          />
          {mode === "register" ? (
            <p className="help">At least 8 characters, including a letter and a number.</p>
          ) : null}
        </div>
        {mode === "register" ? (
          <div>
            <label className="label" htmlFor="confirm_password">Confirm password</label>
            <input id="confirm_password" name="confirm_password" type="password" className="input" autoComplete="new-password" required minLength={8} />
          </div>
        ) : null}

        <button type="submit" className="btn btn-primary w-full" disabled={busy}>
          {busy ? <Loader2 size={16} className="animate-spin" aria-hidden /> : <LockKeyhole size={16} aria-hidden />}
          {mode === "login" ? "Sign in" : "Create consumer account"}
        </button>
      </form>
    </div>
  );
}
