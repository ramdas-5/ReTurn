import { ArrowLeft, CheckCircle2, Route, ShieldCheck, Truck } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { Brand } from "@/components/Brand";
import AuthForm from "@/components/forms/AuthForm";
import { getMe } from "@/lib/server";
import { homeFor } from "@/lib/roles";

export const metadata = { title: "Sign in or create an account" };

export default async function AuthPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  // Render the sign-in form even while the API is unreachable (cold start).
  // A failed sign-in attempt surfaces the connection error inside the form.
  const me = await getMe().catch(() => null);
  if (me) redirect(homeFor(me.user.role));
  const { next } = await searchParams;

  return (
    <main className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <section className="relative hidden flex-col justify-between overflow-hidden bg-ink p-10 text-white lg:flex">
        <div className="pointer-events-none absolute -left-24 bottom-0 h-[420px] w-[420px] rounded-full bg-accent/30 blur-[110px]" aria-hidden="true" />
        <Brand invert />
        <div className="relative">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-lime">Shared logistics, honestly done</p>
          <h1 className="mt-4 max-w-md text-[44px] font-bold leading-[1.03] tracking-tight">
            One route. Multiple deliveries. Less waste.
          </h1>
          <p className="mt-4 max-w-md text-sm leading-6 text-white/65">
            Send a parcel or return a product. A real operations team reviews every order, verifies capacity and
            assigns a driver — no invented tracking or fake instant dispatch.
          </p>
          <div className="mt-8 max-w-md rounded-card border border-white/12 bg-white/[0.04] p-5">
            <ul className="space-y-3 text-[13px] leading-5 text-white/70">
              <li className="flex gap-2"><CheckCircle2 size={15} className="mt-0.5 shrink-0 text-lime" aria-hidden /> Return destinations stay authorised.</li>
              <li className="flex gap-2"><ShieldCheck size={15} className="mt-0.5 shrink-0 text-lime" aria-hidden /> Drivers and vehicles are manager-verified.</li>
              <li className="flex gap-2"><Truck size={15} className="mt-0.5 shrink-0 text-lime" aria-hidden /> Deliveries complete only with captured proof.</li>
              <li className="flex gap-2"><Route size={15} className="mt-0.5 shrink-0 text-lime" aria-hidden /> Shared routes require genuine feasibility.</li>
            </ul>
          </div>
        </div>
        <p className="text-[11px] leading-4 text-white/35">
          Demo data is fictional. Map data © OpenStreetMap contributors. Savings are modelled estimates.
        </p>
      </section>

      <section className="flex flex-col px-5 py-8 sm:px-10">
        <div className="flex items-center justify-between gap-4">
          <div className="lg:hidden"><Brand /></div>
          <Link href="/" className="btn btn-ghost btn-sm ml-auto">
            <ArrowLeft size={15} aria-hidden /> Back to landing
          </Link>
        </div>
        <div className="mx-auto flex w-full max-w-[430px] flex-1 flex-col justify-center py-10">
          <p className="eyebrow">ReTurn account</p>
          <h2 className="mt-2 text-[30px] font-bold leading-tight">Welcome to a calmer route</h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            Sign in, or create a consumer account to send parcels and returns.
          </p>
          <div className="mt-6"><AuthForm nextPath={next} /></div>
          <div className="mt-4 flex items-center justify-between text-xs">
            <Link href="/auth/forgot" className="link">Forgot password?</Link>
            <Link href="/auth/activate" className="link">Activate account</Link>
          </div>
          <p className="mt-5 text-center text-[11px] leading-5 text-muted">
            Sessions use a secure HttpOnly cookie with CSRF protection.
          </p>
        </div>
      </section>
    </main>
  );
}
