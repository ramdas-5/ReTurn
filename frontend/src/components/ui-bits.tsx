"use client";

import { Loader2 } from "lucide-react";
import type { ReactNode } from "react";

export function Button({
  children,
  busy = false,
  className = "btn btn-primary",
  type = "button",
  ...rest
}: {
  children: ReactNode;
  busy?: boolean;
  className?: string;
  type?: "button" | "submit";
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type={type} className={className} disabled={busy || rest.disabled} {...rest}>
      {busy ? <Loader2 size={15} className="animate-spin" aria-hidden /> : null}
      {children}
    </button>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return <p className="text-sm text-muted">{label}</p>;
}

export function ErrorText({ children }: { children: ReactNode }) {
  if (!children) return null;
  return (
    <p className="rounded-control border border-[#f3d1cb] bg-red-soft px-3 py-2 text-sm text-[#8c2f2f]" role="alert">
      {children}
    </p>
  );
}
