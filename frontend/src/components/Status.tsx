import {
  AlertTriangle,
  ArrowLeftRight,
  Ban,
  CheckCircle2,
  Clock3,
  Layers,
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

const DONE = ["delivered", "returned", "completed", "resolved", "valid", "verified"];
const BAD = ["failed", "rejected", "cancelled"];

function StatusIcon({ status }: { status: string }) {
  const common = { size: 13, strokeWidth: 2.2, "aria-hidden": true } as const;
  if (DONE.includes(status)) return <CheckCircle2 {...common} />;
  if (BAD.includes(status)) return <AlertTriangle {...common} />;
  if (["pickup_arrived", "picked_up", "in_transit", "out_for_delivery", "delivery_proof_pending"].includes(status))
    return <Truck {...common} />;
  if (["assigned", "pickup_scheduled"].includes(status)) return <Navigation {...common} />;
  if (["active", "assigned_batch"].includes(status)) return <Layers {...common} />;
  if (status === "cancelled") return <Ban {...common} />;
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
