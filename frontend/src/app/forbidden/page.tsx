import { ShieldAlert } from "lucide-react";
import Link from "next/link";

import { Brand } from "@/components/Brand";
import { getMe } from "@/lib/server";
import { homeFor } from "@/lib/roles";

export const metadata = { title: "Access denied" };

export default async function ForbiddenPage() {
  const me = await getMe();
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-5 text-center">
      <Brand />
      <span className="mt-10 flex h-12 w-12 items-center justify-center rounded-full bg-red-soft text-[#8c2f2f]">
        <ShieldAlert size={22} aria-hidden />
      </span>
      <p className="eyebrow mt-5">403 · Access denied</p>
      <h1 className="mt-2 text-[30px] font-bold">That lane isn&apos;t yours</h1>
      <p className="mt-2 max-w-md text-sm leading-6 text-muted">
        Your account role does not have permission for this view. Authorization is enforced by the ReTurn API, not just
        hidden navigation.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        {me ? (
          <Link href={homeFor(me.user.role)} className="btn btn-primary">
            Return to my dashboard
          </Link>
        ) : (
          <Link href="/auth" className="btn btn-primary">
            Sign in
          </Link>
        )}
        <Link href="/" className="btn btn-secondary">
          Back to landing
        </Link>
      </div>
    </main>
  );
}
