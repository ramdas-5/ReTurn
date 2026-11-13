import { AlertTriangle, CheckCircle2, Clock3, MapPin, PackageCheck, Truck } from "lucide-react";

import { formatDateTime } from "@/lib/format";
import type { TrackingEvent } from "@/lib/types";

const LABELS: Record<string, string> = {
  request_created: "Request submitted",
  assigned: "Assigned to a batch",
  partner_accepted: "Partner accepted",
  pickup_arrived: "Arrived at pickup",
  picked_up: "Parcel collected",
  in_transit: "In transit",
  delivered: "Delivered",
  failed: "Delivery issue recorded",
};

function EventIcon({ type }: { type: string }) {
  const common = { size: 14, "aria-hidden": true } as const;
  if (type === "delivered") return <CheckCircle2 {...common} />;
  if (type === "failed") return <AlertTriangle {...common} />;
  if (type === "in_transit") return <Truck {...common} />;
  if (type === "picked_up") return <PackageCheck {...common} />;
  if (type === "pickup_arrived") return <MapPin {...common} />;
  return <Clock3 {...common} />;
}

export default function Timeline({
  events,
  emptyMessage = "Your parcel journey will appear here after you submit a request.",
}: {
  events: TrackingEvent[];
  emptyMessage?: string;
}) {
  if (!events?.length) {
    return <p className="rounded-control bg-surface-muted px-4 py-5 text-sm text-muted">{emptyMessage}</p>;
  }

  return (
    <ol className="relative space-y-0" aria-label="Parcel tracking timeline">
      {events.map((event, index) => {
        const isLast = index === events.length - 1;
        const isProblem = event.event_type === "failed";
        return (
          <li key={event.id} className="relative flex gap-4 pb-6 last:pb-0">
            {!isLast ? <span className="timeline-line" aria-hidden="true" /> : null}
            <span
              className={`relative z-10 mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border ${
                isProblem
                  ? "border-[#f3d1cb] bg-red-soft text-[#8c2f2f]"
                  : "border-[#c3e9da] bg-accent-soft text-accent-strong"
              }`}
            >
              <EventIcon type={event.event_type} />
            </span>
            <div className="min-w-0 pt-0.5">
              <p className="text-sm font-medium">{LABELS[event.event_type] ?? event.event_type.replaceAll("_", " ")}</p>
              {event.notes ? <p className="mt-0.5 text-[13px] leading-5 text-muted">{event.notes}</p> : null}
              <p className="mt-1 text-[11px] text-muted">
                {formatDateTime(event.created_at)} · {event.actor_name}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
