import { Circle, Square } from "lucide-react";

import RouteMap from "@/components/RouteMap";
import { StatusBadge } from "@/components/Status";
import { formatDateTime, formatKm } from "@/lib/format";
import type { Batch, BatchStop } from "@/lib/types";

export function BatchStopsList({
  stops,
  compact = false,
  showLoad = true,
}: {
  stops: BatchStop[];
  compact?: boolean;
  showLoad?: boolean;
}) {
  if (stops.length === 0) {
    return <p className="rounded-control bg-surface-muted px-4 py-4 text-sm text-muted">No stops recorded.</p>;
  }
  return (
    <ol className="space-y-1" aria-label="Ordered route stops">
      {stops.map((stop, index) => (
        <li key={stop.id} className="relative flex gap-3 pb-4 last:pb-0">
          {index < stops.length - 1 ? (
            <span className="absolute left-[15px] top-8 h-[calc(100%-1.5rem)] w-px bg-line" aria-hidden="true" />
          ) : null}
          <span
            className={`relative z-10 mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-[11px] font-bold ${
              stop.kind === "dropoff"
                ? "border-[#cfe4f3] bg-blue-soft text-[#1d5580]"
                : "border-[#c3e9da] bg-accent-soft text-accent-strong"
            }`}
            title={stop.kind === "pickup" ? "Pickup" : "Drop-off"}
          >
            {stop.sequence}
          </span>
          <div className="min-w-0 flex-1 pt-0.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[13px] font-semibold">
                {stop.kind === "pickup" ? "Pickup" : "Drop-off"}
              </span>
              {stop.request?.code ? <span className="mono text-[11px] text-muted">{stop.request.code}</span> : null}
              <StatusBadge status={stop.status === "done" ? "completed" : stop.status === "arrived" ? "in_progress" : stop.status} />
            </div>
            <p className="mt-0.5 text-sm leading-5">{stop.location.label}</p>
            <p className="text-xs text-muted">
              {formatDateTime(stop.planned_arrival)} · {stop.location.area}
              {stop.request?.parcel_code ? ` · ${stop.request.parcel_code}` : ""}
            </p>
            {!compact ? (
              <p className="mt-1 text-[11px] text-muted">
                Leg {formatKm(stop.leg_distance_km)} · {stop.leg_duration_minutes} min travel ·{" "}
                {stop.service_minutes} min service
                {showLoad ? ` · load after stop ${stop.load_weight_kg.toFixed(1)} kg` : ""}
              </p>
            ) : null}
          </div>
          <div className="hidden shrink-0 pt-1 text-muted sm:block" aria-hidden="true">
            {stop.kind === "pickup" ? <Circle size={13} /> : <Square size={13} />}
          </div>
        </li>
      ))}
    </ol>
  );
}

export function BatchMap({
  batch,
  height = "360px",
  activeSequence,
}: {
  batch: Batch;
  height?: string;
  activeSequence?: number;
}) {
  const stops = batch.stops.map((stop) => ({
    id: stop.id,
    code: stop.request?.code,
    label: stop.location.label,
    area: stop.location.area,
    latitude: stop.location.latitude,
    longitude: stop.location.longitude,
    kind: stop.kind,
    sequence: stop.sequence,
    status: stop.status,
  }));
  return (
    <div className="space-y-2">
      <RouteMap
        stops={stops}
        geometry={batch.geometry}
        geometrySource={batch.geometry_source}
        activeSequence={activeSequence}
        height={height}
      />
      <p className="text-[11px] leading-4 text-muted">
        {batch.geometry_source === "osrm"
          ? "Road geometry from the configured OSRM service. Times remain modelled forecasts, not live GPS."
          : "Illustrative connectors — estimated, not road navigation. Stop order and pickup-before-delivery rules still apply."}
      </p>
    </div>
  );
}

export function BatchStopsLegend() {
  return (
    <div className="flex flex-wrap items-center gap-4 text-[11px] text-muted">
      <span className="inline-flex items-center gap-1.5">
        <span className="flex h-4 w-4 items-center justify-center rounded-full bg-accent text-[8px] font-bold text-white">1</span>
        Pickup
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="flex h-4 w-4 items-center justify-center rounded-[4px] bg-[#2c6ca2] text-[8px] font-bold text-white">2</span>
        Drop-off
      </span>
      <span>Dashed connector = estimated</span>
    </div>
  );
}
