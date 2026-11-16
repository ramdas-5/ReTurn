"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { ApiError, apiPost } from "@/lib/api";

function ResetForm() {
  const params = useSearchParams();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const values = Object.fromEntries(new FormData(event.currentTarget).entries());
    try {
      await apiPost("/auth/reset-password", { ...values, token: params.get("token") ?? values.token });
      router.push("/auth");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Reset failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="card card-pad mt-6 space-y-4">
      {error ? <p className="text-sm text-danger" role="alert">{error}</p> : null}
      <div>
        <label className="label" htmlFor="token">Reset token</label>
        <input id="token" name="token" className="input" defaultValue={params.get("token") ?? ""} required minLength={10} />
      </div>
      <div>
        <label className="label" htmlFor="new_password">New password</label>
        <input id="new_password" name="new_password" type="password" className="input" required minLength={8} />
      </div>
      <div>
        <label className="label" htmlFor="confirm_password">Confirm password</label>
        <input id="confirm_password" name="confirm_password" type="password" className="input" required minLength={8} />
      </div>
      <button className="btn btn-primary w-full" disabled={busy}>Reset password</button>
      <p className="text-xs text-muted">Resetting revokes existing sessions.</p>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-5 py-12">
      <p className="eyebrow">Account recovery</p>
      <h1 className="mt-2 text-3xl font-bold">Choose a new password</h1>
      <Suspense fallback={<p className="mt-6 text-sm text-muted">Loading…</p>}>
        <ResetForm />
      </Suspense>
      <Link href="/auth" className="link mt-6 text-sm">Back to sign in</Link>
    </main>
  );
}
