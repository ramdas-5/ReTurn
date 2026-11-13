import type { BatchStatus, ParcelStatus, RequestStatus, ServiceType } from "@/lib/types";

export const TIME_ZONE = "Asia/Kolkata";

export function formatDateTime(value: string | null | undefined, timeZone = TIME_ZONE): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
    timeZone,
  }).format(new Date(value));
}

export function formatDate(value: string | null | undefined, timeZone = TIME_ZONE): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-IN", {
    weekday: "short",
    day: "2-digit",
    month: "short",
    timeZone,
  }).format(new Date(value));
}

export function formatTime(value: string | null | undefined, timeZone = TIME_ZONE): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
    timeZone,
  }).format(new Date(value));
}

export function formatWindow(start: string, end: string, timeZone = TIME_ZONE): string {
  return `${formatDate(start, timeZone)}, ${formatTime(start, timeZone)} – ${formatTime(end, timeZone)}`;
}

export function relativeTime(value: string | null | undefined): string {
  if (!value) return "—";
  const diffMs = Date.now() - new Date(value).getTime();
  const minutes = Math.round(diffMs / 60000);
  if (Math.abs(minutes) < 1) return "just now";
  if (Math.abs(minutes) < 60) return `${minutes > 0 ? "" : "in "}${Math.abs(minutes)} min${minutes > 0 ? " ago" : ""}`;
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return `${hours > 0 ? "" : "in "}${Math.abs(hours)} hr${hours > 0 ? " ago" : ""}`;
  const days = Math.round(hours / 24);
  return `${days > 0 ? "" : "in "}${Math.abs(days)} day${Math.abs(days) === 1 ? "" : "s"}${days > 0 ? " ago" : ""}`;
}

export function formatKm(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${Number(value).toFixed(digits)} km`;
}

export function formatWeight(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${Number(value).toFixed(value < 1 ? 2 : 1)} kg`;
}

export function formatVolume(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${Number(value).toFixed(3)} m³`;
}

export function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}

export type StatusTone = "neutral" | "blue" | "teal" | "amber" | "green" | "red";

const TONES: Record<string, StatusTone> = {
  pending_matching: "neutral",
  pending: "neutral",
  proposed: "blue",
  offered: "blue",
  batched: "blue",
  assigned: "teal",
  partner_accepted: "teal",
  accepted: "teal",
  pickup_arrived: "amber",
  picked_up: "amber",
  in_transit: "amber",
  in_progress: "amber",
  delivered: "green",
  completed: "green",
  cancelled: "neutral",
  failed: "red",
  declined: "neutral",
  open: "amber",
  in_review: "blue",
  resolved: "green",
  available: "green",
  unavailable: "neutral",
  on_route: "amber",
  verified: "green",
  rejected: "red",
};

export function statusTone(status: string): StatusTone {
  return TONES[status] ?? "neutral";
}

const LABELS: Record<string, string> = {
  pending_matching: "Pending match",
  batched: "In proposed batch",
  assigned: "Partner accepted",
  in_progress: "On route",
  completed: "Completed",
  cancelled: "Cancelled",
  failed: "Failed",
  proposed: "Proposed",
  offered: "Offer sent",
  accepted: "Accepted",
  declined: "Declined",
  pending: "Pending",
  partner_accepted: "Partner accepted",
  pickup_arrived: "At pickup",
  picked_up: "Picked up",
  in_transit: "In transit",
  delivered: "Delivered",
  open: "Open",
  in_review: "In review",
  resolved: "Resolved",
  available: "Available",
  unavailable: "Unavailable",
  on_route: "On route",
  verified: "Verified",
  rejected: "Rejected",
};

export function statusLabel(status: string): string {
  return LABELS[status] ?? status.replaceAll("_", " ");
}

export function serviceLabel(type: ServiceType | string): string {
  return type === "return" ? "Product return" : "Parcel delivery";
}

export function serviceShortLabel(type: ServiceType | string): string {
  return type === "return" ? "Return" : "Parcel";
}

export function destinationLabel(request: {
  type: ServiceType | string;
  destination: { label: string; area: string };
  return_detail?: { authorized_hub_name: string } | null;
  recipient?: { name: string } | null;
}): string {
  if (request.type === "return") {
    return request.return_detail?.authorized_hub_name ?? request.destination.label;
  }
  return request.recipient?.name
    ? `${request.destination.area} · ${request.recipient.name}`
    : request.destination.label;
}

export function initials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function isActiveRequest(status: RequestStatus): boolean {
  return ["pending_matching", "batched", "assigned", "in_progress"].includes(status);
}

export function isActiveBatch(status: BatchStatus): boolean {
  return ["proposed", "offered", "accepted", "in_progress"].includes(status);
}

const PARCEL_ACTION_LABELS: Partial<Record<ParcelStatus, string>> = {
  partner_accepted: "Mark arrived at pickup",
  pickup_arrived: "Confirm pickup",
  picked_up: "Start transit",
  in_transit: "Confirm delivered",
};

const NEXT_PARCEL_EVENTS: Partial<Record<ParcelStatus, string>> = {
  partner_accepted: "pickup_arrived",
  pickup_arrived: "picked_up",
  picked_up: "in_transit",
  in_transit: "delivered",
};

export function parcelActionLabel(status: ParcelStatus): string | null {
  return PARCEL_ACTION_LABELS[status] ?? null;
}

export function nextParcelEvent(status: ParcelStatus): string | null {
  return NEXT_PARCEL_EVENTS[status] ?? null;
}
