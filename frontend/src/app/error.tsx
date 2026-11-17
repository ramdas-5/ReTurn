"use client";

import { AlertTriangle } from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";

import { Brand } from "@/components/Brand";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("ReTurn page error:", error.message);
  }, [error]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-5 text-center">
      <Brand />
      <span className="mt-10 flex h-12 w-12 items-center justify-center rounded-full bg-amber-soft text-amber-ink">
        <AlertTriangle size={22} aria-hidden />
      </span>
      <p className="eyebrow mt-5">Something interrupted the route</p>
      <h1 className="mt-2 text-3xl font-bold">This view couldn&apos;t be loaded</h1>
      <p className="mt-2 max-w-lg text-sm leading-6 text-muted">
        {error.message || "An unexpected error occurred."} If the ReTurn API is not running, start the Flask service and
        try again. No partial changes are saved by a failed read.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        <button type="button" className="btn btn-primary" onClick={reset}>
          Try again
        </button>
        <Link href="/" className="btn btn-secondary">
          Back to ReTurn
        </Link>
      </div>
    </main>
  );
}
