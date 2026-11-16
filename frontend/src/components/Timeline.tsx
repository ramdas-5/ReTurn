import { AlertTriangle, CheckCircle2, Clock3, MapPin, PackageCheck, Truck } from "lucide-react";

import { formatDateTime } from "@/lib/format";
import type { StatusEvent } from "@/lib/types";

function EventIcon({ status }: { status: string }) {
  const common = { size: 14, "aria-hidden": true } as const;
  if (["delivered", "returned"].includes(status)) return <CheckCircle2 {...common} />;
  if (status === "failed") return <AlertTriangle {...common} />;
  if (["in_transit", "out_for_delivery"].includes(status)) return <Truck {...common} />;
  if (status === "picked_up") return <PackageCheck {...common} />;
  if (status === "pickup_arrived") return <MapPin {...common} />;
  return <Clock3 {...common} />;
}

export default function Timeline({
  events,
  emptyMessage = "The parcel journey will appear here after submission.",
}: {
  events: StatusEvent[];
  emptyMessage?: string;
}) {
  if (!events?.length) {
    return <p className="rounded-control bg-surface-muted px-4 py-5 text-sm text-muted">{emptyMessage}</p>;
  }

  return (
    <ol className="relative space-y-0" aria-label="Order tracking timeline">
      {events.map((event, index) => {
        const isLast = index === events.length - 1;
        return (
          <li key={event.id} className="relative flex gap-4 pb-6 last:pb-0">
            {!isLast ? <span className="timeline-line" aria-hidden="true" /> : null}
            <span className="relative z-10 mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-[#c3e9da] bg-accent-soft text-accent-strong">
              <EventIcon status={event.to_status} />
            </span>
            <div className="min-w-0 pt-0.5">
              <p className="text-sm font-medium">{event.to_label}</p>
              {event.reason ? (
                <p className="mt-0.5 text-[13px] leading-5 text-muted">{event.reason}</p>
              ) : null}
              <p className="mt-1 text-[11px] text-muted">
                {formatDateTime(event.created_at)} · {event.actor?.full_name ?? "System"} · {event.source}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
