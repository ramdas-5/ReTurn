import {
  AlertTriangle,
  ArrowLeftRight,
  Ban,
  CheckCircle2,
  Clock3,
  Layers,
  MapPin,
  Navigation,
  Package,
  Truck,
} from "lucide-react";

import { cn } from "@/lib/cn";
import { statusLabel, statusTone, type StatusTone } from "@/lib/format";

const TONE_CLASS: Record<StatusTone, string> = {
  neutral: "chip-neutral",
  blue: "chip-blue",
  teal: "chip-teal",
  amber: "chip-amber",
  green: "chip-green",
  red: "chip-red",
};

function StatusIcon({ status }: { status: string }) {
  const common = { size: 13, strokeWidth: 2.2, "aria-hidden": true } as const;
  if (["delivered", "completed", "resolved", "verified"].includes(status)) return <CheckCircle2 {...common} />;
  if (["failed", "rejected"].includes(status)) return <AlertTriangle {...common} />;
  if (status === "cancelled") return <Ban {...common} />;
  if (["pickup_arrived", "picked_up", "in_transit", "in_progress", "on_route"].includes(status))
    return <Truck {...common} />;
  if (["assigned", "accepted", "partner_accepted"].includes(status)) return <Navigation {...common} />;
  if (["proposed", "offered", "batched"].includes(status)) return <Layers {...common} />;
  if (status === "open" || status === "in_review") return <MapPin {...common} />;
  return <Clock3 {...common} />;
}

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  return (
    <span className={cn("chip", TONE_CLASS[statusTone(status)], className)}>
      <StatusIcon status={status} />
      {statusLabel(status)}
    </span>
  );
}

export function ServiceBadge({ type }: { type: string }) {
  const isReturn = type === "return";
  return (
    <span className={cn("chip", isReturn ? "chip-teal" : "chip-blue")}>
      {isReturn ? <ArrowLeftRight size={13} aria-hidden /> : <Package size={13} aria-hidden />}
      {isReturn ? "Return" : "Parcel"}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  const tone = severity === "high" ? "chip-red" : severity === "medium" ? "chip-amber" : "chip-neutral";
  return <span className={cn("chip capitalize", tone)}>{severity}</span>;
}

export function VerificationBadge({ status }: { status: string }) {
  const tone =
    status === "verified" ? "chip-green" : status === "rejected" ? "chip-red" : "chip-amber";
  return <span className={cn("chip capitalize", tone)}>{status}</span>;
}
