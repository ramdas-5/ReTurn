"use client";

import "leaflet/dist/leaflet.css";

import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/cn";

export type MapStop = {
  id: string | number;
  code?: string;
  label: string;
  area?: string;
  latitude: number;
  longitude: number;
  kind: "pickup" | "dropoff";
  sequence?: number;
  status?: string;
};

type Geometry = { type: string; coordinates: number[][] } | null;

type LeafletApi = typeof import("leaflet");

/**
 * Leaflet is published as a UMD bundle with no ES `default` export. Depending on
 * how the bundler wraps it, the API can arrive as the module namespace itself, as
 * `module.default`, or as a nested namespace. Resolve whichever object actually
 * exposes `map()` instead of assuming a single shape.
 */
function resolveLeaflet(module: unknown): LeafletApi | null {
  const candidates: unknown[] = [module];
  let current: unknown = module;
  for (let depth = 0; depth < 3; depth += 1) {
    const next = (current as { default?: unknown } | null | undefined)?.default;
    if (!next || next === current) break;
    candidates.push(next);
    current = next;
  }
  for (const candidate of candidates) {
    if (candidate && typeof (candidate as LeafletApi).map === "function") return candidate as LeafletApi;
  }
  return null;
}

export default function RouteMap({
  stops,
  geometry = null,
  geometrySource = "estimated",
  activeSequence,
  height = "380px",
  emptyMessage = "No map coordinates available for this view.",
}: {
  stops: MapStop[];
  geometry?: Geometry;
  geometrySource?: "osrm" | "estimated" | string;
  activeSequence?: number;
  height?: string;
  emptyMessage?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [mapError, setMapError] = useState<string | null>(null);
  const signature = JSON.stringify({ stops, geometry, activeSequence });

  useEffect(() => {
    let cancelled = false;
    let map: import("leaflet").Map | null = null;
    let onResize: (() => void) | null = null;

    async function mount() {
      const leafletModule = await import("leaflet").catch(() => null);
      const L = resolveLeaflet(leafletModule);
      if (cancelled || !containerRef.current || stops.length === 0) return;
      if (!L) {
        setMapError("The map library could not be loaded. Reload the page to try again.");
        return;
      }

      map = L.map(containerRef.current, {
        scrollWheelZoom: false,
        zoomControl: true,
        attributionControl: true,
      });

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).addTo(map);

      const points = stops.map((stop) => [stop.latitude, stop.longitude] as [number, number]);

      if (geometry?.coordinates?.length) {
        L.geoJSON(geometry as GeoJSON.GeoJsonObject, {
          style: {
            color: "#087C60",
            weight: 4,
            opacity: 0.88,
            dashArray: geometrySource === "estimated" ? "7 7" : undefined,
            lineCap: "round",
          },
        }).addTo(map);
      } else if (points.length > 1) {
        L.polyline(points, {
          color: "#087C60",
          weight: 4,
          opacity: 0.8,
          dashArray: "7 7",
        }).addTo(map);
      }

      stops.forEach((stop, index) => {
        const sequence = stop.sequence ?? index + 1;
        const isActive = activeSequence === sequence;
        const isDone = ["done", "delivered", "completed"].includes(stop.status ?? "");
        const icon = L.divIcon({
          className: "rt-stop-icon-wrap",
          html: `<div class="rt-stop-marker ${stop.kind === "dropoff" ? "dropoff" : "pickup"} ${
            isActive ? "is-active" : ""
          } ${isDone && !isActive ? "is-done" : ""}"><span>${sequence}</span></div>`,
          iconSize: isActive ? [36, 36] : [30, 30],
          iconAnchor: isActive ? [18, 18] : [15, 15],
        });
        const marker = L.marker([stop.latitude, stop.longitude], {
          icon,
          title: `${sequence}. ${stop.kind === "pickup" ? "Pickup" : "Drop-off"} — ${stop.label}`,
          keyboard: true,
        }).addTo(map as import("leaflet").Map);

        const popup = document.createElement("div");
        popup.style.minWidth = "170px";
        const heading = document.createElement("p");
        heading.style.margin = "0 0 4px";
        heading.style.fontWeight = "600";
        heading.textContent = `${sequence}. ${stop.kind === "pickup" ? "Pickup" : "Drop-off"}`;
        const label = document.createElement("p");
        label.style.margin = "0";
        label.style.fontSize = "12px";
        label.style.color = "#5E726F";
        label.textContent = stop.label;
        popup.append(heading, label);
        if (stop.code) {
          const code = document.createElement("p");
          code.style.margin = "4px 0 0";
          code.style.fontSize = "11px";
          code.style.fontFamily = "monospace";
          code.style.color = "#274442";
          code.textContent = stop.code;
          popup.appendChild(code);
        }
        marker.bindPopup(popup);
      });

      if (points.length === 1) {
        map.setView(points[0], 13);
      } else if (points.length > 1) {
        map.fitBounds(L.latLngBounds(points), { padding: [32, 32], maxZoom: 14 });
      }

      window.setTimeout(() => map?.invalidateSize(), 180);
      onResize = () => map?.invalidateSize();
      window.addEventListener("resize", onResize);
    }

    setMapError(null);
    void mount().catch((error: unknown) => {
      if (cancelled) return;
      map?.remove();
      map = null;
      setMapError(error instanceof Error ? error.message : "The route map could not be drawn.");
    });

    return () => {
      cancelled = true;
      if (onResize) window.removeEventListener("resize", onResize);
      map?.remove();
      map = null;
    };
    // The serialized signature covers stop/geometry changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature]);

  if (stops.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded-control border border-dashed bg-surface-muted px-6 text-center text-sm text-muted"
        style={{ height }}
      >
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className={cn("relative overflow-hidden rounded-control border")}>
      <div ref={containerRef} style={{ height }} aria-label="Map of ordered pickup and drop-off stops" />
      {mapError ? (
        <div
          role="status"
          className="absolute inset-0 z-[401] flex flex-col items-center justify-center gap-1 bg-surface-muted px-6 text-center"
        >
          <p className="text-sm font-medium text-ink">Map unavailable</p>
          <p className="max-w-sm text-xs leading-5 text-muted">
            {mapError} The ordered stop list is unaffected.
          </p>
        </div>
      ) : null}
      <div className="absolute bottom-2 left-2 z-[400] rounded bg-white/95 px-2 py-1 text-[10px] font-medium text-ink-2 shadow-sm">
        {geometrySource === "osrm" ? "Road route · OSRM" : "Illustrative connectors — estimated, not road navigation"}
      </div>
    </div>
  );
}
