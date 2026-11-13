import Link from "next/link";

import { cn } from "@/lib/cn";

export function RouteMark({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} role="img" aria-label="ReTurn route mark">
      <rect width="40" height="40" rx="11" fill="currentColor" opacity="0.12" />
      <path
        d="M10 27 C 15 27, 14 18, 20 18 S 25 12, 30 12"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
      <circle cx="10" cy="27" r="4" fill="currentColor" />
      <rect x="26" y="8" width="8" height="8" rx="2.2" fill="currentColor" />
      <path d="M20.5 15.5 L 23 13 L 20.5 10.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" opacity="0.7" />
    </svg>
  );
}

export function Brand({
  href = "/",
  invert = false,
  compact = false,
}: {
  href?: string;
  invert?: boolean;
  compact?: boolean;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "inline-flex items-center gap-2.5 font-display text-[22px] font-bold tracking-tight",
        invert ? "text-white" : "text-ink",
      )}
      aria-label="ReTurn home"
    >
      <RouteMark className={cn(compact ? "h-8 w-8" : "h-9 w-9", invert ? "text-lime" : "text-accent")} />
      <span>
        Re<span className={invert ? "text-lime" : "text-accent"}>Turn</span>
      </span>
    </Link>
  );
}
