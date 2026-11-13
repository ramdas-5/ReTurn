import { formatWeight } from "@/lib/format";

export function CompletionBar({
  maxWeight,
  maxVolume,
  referenceWeight,
  referenceVolume,
}: {
  maxWeight: number;
  maxVolume: number;
  referenceWeight: number;
  referenceVolume: number;
}) {
  const weightPct = Math.min(100, Math.round((maxWeight / referenceWeight) * 100));
  const volumePct = Math.min(100, Math.round((maxVolume / referenceVolume) * 100));
  return (
    <div className="space-y-2 rounded-control bg-surface-muted p-3">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted">
        Capacity vs configured reference vehicle
      </p>
      <div>
        <div className="mb-1 flex justify-between gap-2 text-[11px]">
          <span>Weight</span>
          <span className="mono">{formatWeight(maxWeight)}</span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-white">
          <div className="h-full rounded-full bg-accent" style={{ width: `${weightPct}%` }} />
        </div>
      </div>
      <div>
        <div className="mb-1 flex justify-between gap-2 text-[11px]">
          <span>Volume</span>
          <span className="mono">{maxVolume.toFixed(3)} m³</span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-white">
          <div className="h-full rounded-full bg-[#2c6ca2]" style={{ width: `${volumePct}%` }} />
        </div>
      </div>
    </div>
  );
}
