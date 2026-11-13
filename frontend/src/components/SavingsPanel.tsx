import { Leaf, Route } from "lucide-react";

import { Callout, CapacityBar } from "@/components/ui";
import { formatKm } from "@/lib/format";

export function SourceBadge({ source }: { source: string }) {
  return (
    <span className={`chip ${source === "osrm" ? "chip-blue" : "chip-amber"}`}>
      <Route size={12} aria-hidden />
      {source === "osrm" ? "OSRM road routing" : "Estimated (not road navigation)"}
    </span>
  );
}

export default function SavingsPanel({
  baselineKm,
  sharedKm,
  savingsKm,
  savingsPercent,
  fuelSaved,
  co2Saved,
  sourceLabel,
  maxWeight,
  peakWeight,
  maxVolume,
  peakVolume,
  assumptions,
  compact = false,
}: {
  baselineKm: number;
  sharedKm: number;
  savingsKm: number;
  savingsPercent: number;
  fuelSaved?: number;
  co2Saved?: number;
  sourceLabel?: string;
  maxWeight?: number;
  peakWeight?: number;
  maxVolume?: number;
  peakVolume?: number;
  assumptions?: string[];
  compact?: boolean;
}) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-control border bg-surface-muted p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-muted">Separate-trip baseline</p>
          <p className="mono mt-2 text-2xl font-semibold">{formatKm(baselineKm)}</p>
          <p className="mt-1 text-[11px] leading-4 text-muted">One direct pickup → destination per request</p>
        </div>
        <div className="rounded-control border border-[#c3e9da] bg-accent-soft p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-accent-strong">Shared plan</p>
          <p className="mono mt-2 text-2xl font-semibold text-accent-strong">{formatKm(sharedKm)}</p>
          <p className="mt-1 text-[11px] leading-4 text-accent-strong/80">{sourceLabel ?? "Same distance basis"}</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <span className="chip chip-green">
          <Leaf size={12} aria-hidden />
          Estimated distance saved: {formatKm(savingsKm)} ({savingsPercent.toFixed(1)}%)
        </span>
        {fuelSaved !== undefined ? (
          <span className="chip chip-amber">Estimated fuel saved: {fuelSaved.toFixed(2)} L</span>
        ) : null}
        {co2Saved !== undefined ? (
          <span className="chip chip-amber">Estimated CO₂e avoided: {co2Saved.toFixed(2)} kg</span>
        ) : null}
      </div>

      {!compact && maxWeight && peakWeight !== undefined ? (
        <div className="space-y-3 rounded-control border p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">Vehicle load at the heaviest point</p>
          <CapacityBar label="Weight" value={peakWeight} max={maxWeight} unit="kg" />
          {maxVolume && peakVolume !== undefined ? (
            <CapacityBar label="Volume" value={peakVolume} max={maxVolume} unit="m³" />
          ) : null}
        </div>
      ) : null}

      <Callout tone="warning" title="All savings are estimates">
        Figures compare modelled routes on the same assumptions. They are not measured fuel use, verified emissions, or
        a guarantee that a specific number of vehicles was removed from the road.
      </Callout>

      {assumptions?.length ? (
        <details className="rounded-control border bg-surface px-4 py-3 text-sm">
          <summary className="cursor-pointer font-medium">Method and assumptions</summary>
          <ul className="mt-3 space-y-1.5 text-[13px] leading-5 text-muted">
            {assumptions.map((assumption) => (
              <li key={assumption}>• {assumption}</li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}
