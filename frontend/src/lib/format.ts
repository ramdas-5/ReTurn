import type { ServiceType } from "@/lib/types";

export const TIME_ZONE = "Asia/Kolkata";

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
    timeZone: TIME_ZONE,
  }).format(new Date(value));
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-IN", {
    weekday: "short",
    day: "2-digit",
    month: "short",
    timeZone: TIME_ZONE,
  }).format(new Date(value));
}

export function formatWindow(start: string | null, end: string | null): string {
  if (!start || !end) return "—";
  return `${formatDate(start)}, ${new Intl.DateTimeFormat("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
    timeZone: TIME_ZONE,
  }).format(new Date(start))} – ${new Intl.DateTimeFormat("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
    timeZone: TIME_ZONE,
  }).format(new Date(end))}`;
}

export function relativeTime(value: string | null | undefined): string {
  if (!value) return "—";
  const minutes = Math.round((Date.now() - new Date(value).getTime()) / 60000);
  if (Math.abs(minutes) < 1) return "just now";
  if (Math.abs(minutes) < 60) return minutes > 0 ? `${minutes} min ago` : `in ${-minutes} min`;
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return hours > 0 ? `${hours} hr ago` : `in ${-hours} hr`;
  const days = Math.round(hours / 24);
  return days > 0 ? `${days} day${days === 1 ? "" : "s"} ago` : `in ${-days} days`;
}

export function formatKm(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${Number(value).toFixed(digits)} km`;
}

export function formatWeight(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${Number(value).toFixed(value < 1 ? 2 : 1)} kg`;
}

export function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}

export function initials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function serviceLabel(type: ServiceType | string): string {
  return type === "return" ? "Product return" : "Parcel";
}

export type StatusTone = "neutral" | "blue" | "teal" | "amber" | "green" | "red";

const TONES: Record<string, StatusTone> = {
  draft: "neutral",
  submitted: "blue",
  pending_review: "amber",
  awaiting_assignment: "amber",
  assigned: "teal",
  pickup_scheduled: "teal",
  pickup_arrived: "amber",
  picked_up: "amber",
  in_transit: "amber",
  out_for_delivery: "amber",
  delivery_proof_pending: "amber",
  return_in_progress: "amber",
  delivered: "green",
  returned: "green",
  verified: "green",
  valid: "green",
  resolved: "green",
  completed: "green",
  active: "teal",
  cancelled: "neutral",
  failed: "red",
  rejected: "red",
  open: "amber",
  in_review: "blue",
  pending_verification: "amber",
  pending: "neutral",
  assigned_batch: "blue",
  available: "green",
  busy: "amber",
  on_break: "blue",
  off_duty: "neutral",
  unavailable: "neutral",
  live_recent: "green",
  stale: "amber",
  unavailable_tracking: "neutral",
};

export function statusTone(status: string): StatusTone {
  return TONES[status] ?? "neutral";
}

const LABELS: Record<string, string> = {
  pending_review: "Pending review",
  awaiting_assignment: "Awaiting assignment",
  pickup_scheduled: "Pickup scheduled",
  pickup_arrived: "At pickup",
  picked_up: "Picked up",
  in_transit: "In transit",
  out_for_delivery: "Out for delivery",
  delivery_proof_pending: "Proof pending",
  return_in_progress: "Return in progress",
  pending_verification: "Pending verification",
  assigned_batch: "Batch assigned",
  off_duty: "Off duty",
  on_break: "On break",
  live_recent: "Live recent",
};

export function statusLabel(status: string): string {
  return LABELS[status] ?? status.replaceAll("_", " ");
}
