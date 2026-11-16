"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiError, apiPost } from "@/lib/api";

export default function ActivatePage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const values = Object.fromEntries(new FormData(event.currentTarget).entries());
    try {
      await apiPost("/auth/activate", values);
      router.push("/auth");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Activation failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-5 py-12">
      <p className="eyebrow">Driver & staff onboarding</p>
      <h1 className="mt-2 text-3xl font-bold">Activate your account</h1>
      <p className="mt-2 text-sm text-muted">
        Use the one-time activation token provided by your ReTurn administrator, then choose your password.
      </p>
      <form onSubmit={submit} className="card card-pad mt-6 space-y-4">
        {error ? <p className="text-sm text-danger" role="alert">{error}</p> : null}
        <div>
          <label className="label" htmlFor="token">Activation token</label>
          <input id="token" name="token" className="input" required minLength={10} />
        </div>
        <div>
          <label className="label" htmlFor="new_password">New password</label>
          <input id="new_password" name="new_password" type="password" className="input" required minLength={8} />
        </div>
        <div>
          <label className="label" htmlFor="confirm_password">Confirm password</label>
          <input id="confirm_password" name="confirm_password" type="password" className="input" required minLength={8} />
        </div>
        <button className="btn btn-primary w-full" disabled={busy}>Activate & sign in</button>
      </form>
    </main>
  );
}
