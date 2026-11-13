import Link from "next/link";

import { Brand, RouteMark } from "@/components/Brand";

export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-5 text-center">
      <Brand />
      <RouteMark className="mt-10 h-14 w-14 text-accent" />
      <p className="eyebrow mt-6">404 · Route not found</p>
      <h1 className="mt-2 text-[32px] font-bold">This stop isn&apos;t on the map</h1>
      <p className="mt-2 max-w-md text-sm leading-6 text-muted">
        The page or record may have moved, or your account may not have been intended for this link. Use a safe return
        path below.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        <Link href="/" className="btn btn-primary">Back to ReTurn</Link>
        <Link href="/auth" className="btn btn-secondary">Sign in</Link>
      </div>
    </main>
  );
}
