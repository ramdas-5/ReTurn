import Link from "next/link";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  back,
}: {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  back?: { href: string; label: string };
}) {
  return (
    <header className="mb-6 flex flex-col gap-4 sm:mb-8 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {back ? (
          <Link href={back.href} className="mb-2 inline-flex items-center gap-1 text-xs text-muted hover:text-ink">
            <span aria-hidden="true">←</span> {back.label}
          </Link>
        ) : null}
        {eyebrow ? <p className="eyebrow mb-2">{eyebrow}</p> : null}
        <h1 className="text-[28px] font-bold leading-tight sm:text-[34px]">{title}</h1>
        {description ? (
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2 sm:justify-end">{actions}</div> : null}
    </header>
  );
}

export function SectionHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 className="section-title">{title}</h2>
        {description ? <p className="mt-1 text-sm text-muted">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function Card({
  children,
  className,
  id,
  as: Tag = "div",
}: {
  children: ReactNode;
  className?: string;
  id?: string;
  as?: "div" | "section" | "article" | "aside";
}) {
  return <Tag id={id} className={cn("card", className)}>{children}</Tag>;
}

export function StatCard({
  label,
  value,
  hint,
  icon,
  tone = "default",
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  tone?: "default" | "accent" | "amber" | "red" | "blue";
}) {
  const toneClass = {
    default: "bg-surface-muted text-ink-2",
    accent: "bg-accent-soft text-accent-strong",
    amber: "bg-amber-soft text-[#8a5a12]",
    red: "bg-red-soft text-[#8c2f2f]",
    blue: "bg-blue-soft text-[#1d5580]",
  }[tone];
  return (
    <div className="card card-pad">
      <div className="flex items-start justify-between gap-3">
        <p className="text-[12px] font-medium uppercase tracking-wider text-muted">{label}</p>
        {icon ? <span className={cn("rounded-lg p-1.5", toneClass)}>{icon}</span> : null}
      </div>
      <p className="stat-value mt-3">{value}</p>
      {hint ? <p className="mt-2 text-xs leading-5 text-muted">{hint}</p> : null}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-card border border-dashed bg-surface px-6 py-12 text-center">
      {icon ? (
        <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-accent-soft text-accent-strong">
          {icon}
        </div>
      ) : null}
      <h3 className="text-base font-semibold">{title}</h3>
      <p className="mt-1 max-w-md text-sm leading-6 text-muted">{description}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function Callout({
  tone = "neutral",
  title,
  children,
}: {
  tone?: "neutral" | "accent" | "warning" | "info" | "danger";
  title?: string;
  children: ReactNode;
}) {
  const classes = {
    neutral: "border-line bg-surface-muted text-ink-2",
    accent: "border-[#c3e9da] bg-accent-soft text-accent-strong",
    warning: "border-[#f3ddb3] bg-amber-soft text-[#7a4d0d]",
    info: "border-[#cfe4f3] bg-blue-soft text-[#1d5580]",
    danger: "border-[#f3d1cb] bg-red-soft text-[#8c2f2f]",
  }[tone];
  return (
    <div className={cn("rounded-control border px-4 py-3 text-sm leading-6", classes)}>
      {title ? <p className="mb-1 font-semibold">{title}</p> : null}
      {children}
    </div>
  );
}

export function Field({
  label,
  htmlFor,
  hint,
  error,
  children,
  className,
}: {
  label: string;
  htmlFor?: string;
  hint?: string;
  error?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <label className="label" htmlFor={htmlFor}>
        {label}
      </label>
      {children}
      {error ? (
        <p className="error-text" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="help">{hint}</p>
      ) : null}
    </div>
  );
}

export function SkeletonRows({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-hidden="true">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="skeleton h-16 w-full" />
      ))}
    </div>
  );
}

export function CapacityBar({
  label,
  value,
  max,
  unit,
}: {
  label: string;
  value: number;
  max: number;
  unit: string;
}) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-3 text-xs">
        <span className="font-medium text-ink-2">{label}</span>
        <span className="mono text-muted">
          {value.toFixed(unit === "kg" ? 1 : 3)} / {max.toFixed(unit === "kg" ? 0 : 3)} {unit}
        </span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-surface-muted"
        role="img"
        aria-label={`${label}: ${pct}% of vehicle capacity used`}
      >
        <div
          className={cn("h-full rounded-full", pct > 90 ? "bg-[#b74444]" : pct > 65 ? "bg-[#e8a33c]" : "bg-accent")}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function Mono({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cn("mono text-[12px]", className)}>{children}</span>;
}

export function RouteLine({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 120 24" className={cn("h-6 w-28", className)} aria-hidden="true">
      <path d="M4 18 C 30 18, 32 6, 60 6 S 88 18, 96 18" fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray="5 4" />
      <circle cx="4" cy="18" r="4" fill="currentColor" />
      <rect x="92" y="14" width="8" height="8" rx="2" fill="currentColor" />
    </svg>
  );
}
