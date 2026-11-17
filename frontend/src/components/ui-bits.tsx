"use client";

import { Loader2 } from "lucide-react";
import type { ReactNode } from "react";

export function Button({
  children,
  busy = false,
  className = "btn btn-primary",
  type = "button",
  disabled,
  ...rest
}: {
  children: ReactNode;
  busy?: boolean;
  className?: string;
  type?: "button" | "submit";
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...rest}
      type={type}
      className={className}
      aria-busy={busy || undefined}
      disabled={busy || disabled}
    >
      {busy ? <Loader2 size={15} className="animate-spin" aria-hidden /> : null}
      {children}
    </button>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <p className="text-sm text-muted" role="status">
      {label}
    </p>
  );
}

export function ErrorText({ children }: { children: ReactNode }) {
  if (!children) return null;
  return (
    <p
      className="rounded-control border border-red-border bg-red-soft px-3 py-2 text-sm text-red-ink"
      role="alert"
    >
      {children}
    </p>
  );
}
