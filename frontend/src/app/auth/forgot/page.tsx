"use client";

import Link from "next/link";
import { useState } from "react";

import { apiPost } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [message, setMessage] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    try {
      const result = await apiPost<{ ok: boolean; message: string; reset_token?: string }>(
        "/auth/forgot-password",
        data,
      );
      setMessage(result.message);
      setToken(result.reset_token ?? null);
    } catch {
      setMessage("If that email has an account, reset instructions have been issued.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-5 py-12">
      <p className="eyebrow">Account recovery</p>
      <h1 className="mt-2 text-3xl font-bold">Forgot your password?</h1>
      <p className="mt-2 text-sm text-muted">
        We issue a single-use reset token. In development the token is returned below; in production it would be delivered by email.
      </p>
      <form onSubmit={submit} className="card card-pad mt-6 space-y-4">
        <div>
          <label className="label" htmlFor="email">Email</label>
          <input id="email" name="email" type="email" className="input" required />
        </div>
        <button className="btn btn-primary w-full" disabled={busy}>Request reset</button>
      </form>
      {message ? <p className="mt-4 text-sm text-muted">{message}</p> : null}
      {token ? (
        <div className="mt-3 rounded-control border bg-surface-tint p-3 text-xs">
          <p className="font-semibold">Development reset token</p>
          <p className="mono mt-1 break-all">{token}</p>
          <Link className="link mt-2 inline-block" href={`/auth/reset?token=${encodeURIComponent(token)}`}>Continue to reset</Link>
        </div>
      ) : null}
      <Link href="/auth" className="link mt-6 text-sm">Back to sign in</Link>
    </main>
  );
}
