"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  Loader2,
  Route,
  Sparkles,
  X,
} from "lucide-react";

import { Callout, CapacityBar } from "@/components/ui";
import { StatusBadge } from "@/components/Status";
import { ApiError, apiPost } from "@/lib/api";
import { formatDateTime, formatKm, serviceShortLabel } from "@/lib/format";
import type { Batch, PreviewGroup, PreviewResult } from "@/lib/types";

export default function MatchingConsole() {
  const router = useRouter();
  const [result, setResult] = useState<PreviewResult | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [partnerId, setPartnerId] = useState<string>("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<"preview" | "commit" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<Batch | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [settings, setSettings] = useState({
    max_group_size: 3,
    max_pickup_radius_km: 8,
    max_detour_km: 9,
    min_savings_pct: 12,
  });

  async function preview() {
    setBusy("preview");
    setError(null);
    setCreated(null);
    setResult(null);
    setSelected(null);
    try {
      const data = await apiPost<PreviewResult>("/matching/preview", { params: settings });
      setResult(data);
      const first = data.groups[0];
      if (first) {
        setSelected(first.group_key);
        setPartnerId(first.partner_options[0] ? String(first.partner_options[0].partner_id) : "");
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Matching preview failed.");
    } finally {
      setBusy(null);
    }
  }

  async function commit(group: PreviewGroup) {
    setBusy("commit");
    setError(null);
    try {
      const batch = await apiPost<Batch>("/matching/commit", {
        request_ids: group.request_ids,
        partner_id: partnerId ? Number(partnerId) : undefined,
        preview_run_id: result?.run_id ?? undefined,
        note: note || undefined,
        params: settings,
      });
      setCreated(batch);
      setResult(null);
      setSelected(null);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Batch could not be created.");
    } finally {
      setBusy(null);
    }
  }

  const selectedGroup = result?.groups.find((group) => group.group_key === selected) ?? null;

  return (
    <section className="card card-pad" id="matching">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="eyebrow">Matching engine</p>
          <h2 className="mt-1 text-[22px] font-bold">Find compatible requests</h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">
            Rule-based feasibility: pickup windows, deadlines, pickup-before-delivery, capacity at every stop, handling,
            service area, detour and a positive estimated saving. Rejections are shown with reasons.
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => setShowSettings((value) => !value)}
            aria-expanded={showSettings}
          >
            <ChevronDown size={14} aria-hidden /> Settings
          </button>
          <button type="button" className="btn btn-primary" onClick={preview} disabled={busy !== null}>
            {busy === "preview" ? <Loader2 size={16} className="animate-spin" aria-hidden /> : <Sparkles size={16} aria-hidden />}
            Find compatible requests
          </button>
        </div>
      </div>

      {showSettings ? (
        <div className="mt-4 grid gap-3 rounded-control border bg-surface-muted p-4 sm:grid-cols-4">
          <label className="text-xs font-medium text-ink-2">
            Max group size
            <select
              className="input mt-1"
              value={settings.max_group_size}
              onChange={(event) => setSettings({ ...settings, max_group_size: Number(event.target.value) })}
            >
              <option value={2}>2 requests</option>
              <option value={3}>3 requests</option>
              <option value={4}>4 requests</option>
            </select>
          </label>
          <label className="text-xs font-medium text-ink-2">
            Pickup radius (km)
            <input
              className="input mt-1"
              type="number"
              min={1}
              max={30}
              step={0.5}
              value={settings.max_pickup_radius_km}
              onChange={(event) => setSettings({ ...settings, max_pickup_radius_km: Number(event.target.value) })}
            />
          </label>
          <label className="text-xs font-medium text-ink-2">
            Max detour (km)
            <input
              className="input mt-1"
              type="number"
              min={0}
              max={40}
              step={0.5}
              value={settings.max_detour_km}
              onChange={(event) => setSettings({ ...settings, max_detour_km: Number(event.target.value) })}
            />
          </label>
          <label className="text-xs font-medium text-ink-2">
            Min saving (%)
            <input
              className="input mt-1"
              type="number"
              min={0}
              max={80}
              step={1}
              value={settings.min_savings_pct}
              onChange={(event) => setSettings({ ...settings, min_savings_pct: Number(event.target.value) })}
            />
          </label>
          <p className="text-[11px] leading-4 text-muted sm:col-span-4">
            These thresholds are configuration for this run, not universal optimums. Feasibility is recomputed again on
            commit in a database transaction.
          </p>
        </div>
      ) : null}

      {error ? (
        <div className="mt-4">
          <Callout tone="danger">{error}</Callout>
        </div>
      ) : null}

      {created ? (
        <div className="mt-4">
          <Callout tone="accent" title={`Proposed batch ${created.code} created`}>
            {created.request_count ?? created.requests.length} requests reserved. Estimated saving{" "}
            {formatKm(created.savings_km)} ({created.savings_percent.toFixed(1)}%).{" "}
            {created.partner
              ? `Offered to ${created.partner.name}.`
              : "No partner assigned yet — offer it from the batch list below."}{" "}
            This is an estimate based on modelled routes.
          </Callout>
        </div>
      ) : null}

      {result ? (
        <div className="mt-5 space-y-5">
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
            <span className="chip chip-neutral">{result.pending_count} pending requests analysed</span>
            <span className={`chip ${result.distance_source === "osrm" ? "chip-blue" : "chip-amber"}`}>
              <Route size={12} aria-hidden />
              {result.distance_source_label}
            </span>
            <span>Run #{result.run_id ?? "—"} · {formatDateTime(result.generated_at)}</span>
          </div>

          {result.groups.length === 0 ? (
            <Callout tone="warning" title="No feasible batch right now">
              Nearby does not always mean compatible. Check the rejection reasons below; a request can be individually
              valid but still have no profitable shared route.
            </Callout>
          ) : null}

          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
            <div className="space-y-3">
              {result.groups.map((group) => {
                const isSelected = group.group_key === selected;
                return (
                  <article
                    key={group.group_key}
                    className={`rounded-card border p-4 transition ${
                      isSelected ? "border-accent bg-accent-soft/40 ring-1 ring-accent" : "bg-surface"
                    }`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
                          Candidate group
                        </p>
                        <p className="mt-0.5 font-semibold">
                          {group.requests.map((request) => request.code).join(" + ")}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {group.requests.map((request) => (
                          <span key={request.id} className={`chip ${request.type === "return" ? "chip-teal" : "chip-blue"}`}>
                            {serviceShortLabel(request.type)}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className="mt-3 grid gap-2 text-[13px] sm:grid-cols-3">
                      <div>
                        <p className="text-[10px] uppercase tracking-wide text-muted">Shared route</p>
                        <p className="mono mt-0.5 font-semibold">{formatKm(group.distance_km)}</p>
                      </div>
                      <div>
                        <p className="text-[10px] uppercase tracking-wide text-muted">Separate trips</p>
                        <p className="mono mt-0.5">{formatKm(group.baseline_km)}</p>
                      </div>
                      <div>
                        <p className="text-[10px] uppercase tracking-wide text-muted">Estimated saving</p>
                        <p className="mono mt-0.5 font-semibold text-accent-strong">
                          {formatKm(group.savings_km)} · {group.savings_percent.toFixed(1)}%
                        </p>
                      </div>
                    </div>

                    <ol className="mt-3 space-y-1.5 border-t pt-3">
                      {group.stops.map((stop, index) => (
                        <li key={`${stop.request_id}-${stop.kind}`} className="flex items-start gap-2 text-[13px]">
                          <span
                            className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[9px] font-bold text-white ${
                              stop.kind === "pickup" ? "bg-accent" : "bg-[#2c6ca2]"
                            }`}
                          >
                            {index + 1}
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="font-medium">{stop.kind === "pickup" ? "Pickup" : "Drop-off"}</span>{" "}
                            <span className="text-muted">· {stop.location.area}</span>
                            <span className="mono ml-1 text-[10px] text-muted">{stop.request_code}</span>
                            <span className="block text-[11px] text-muted">
                              ETA {formatDateTime(stop.arrival)} · leg {formatKm(stop.leg_distance_km)}
                            </span>
                          </span>
                        </li>
                      ))}
                    </ol>

                    <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t pt-3">
                      <button
                        type="button"
                        className={`btn btn-sm ${isSelected ? "btn-primary" : "btn-secondary"}`}
                        onClick={() => {
                          setSelected(group.group_key);
                          setPartnerId(group.partner_options[0] ? String(group.partner_options[0].partner_id) : "");
                        }}
                      >
                        {isSelected ? <Check size={14} aria-hidden /> : null}
                        {isSelected ? "Selected" : "Select group"}
                      </button>
                      <span className="text-[11px] text-muted">
                        Peak {group.max_load_weight_kg.toFixed(1)} kg / {group.max_load_volume_m3.toFixed(3)} m³
                      </span>
                    </div>
                  </article>
                );
              })}
            </div>

            <div className="space-y-4">
              {selectedGroup ? (
                <div className="rounded-card border bg-surface p-4">
                  <h3 className="text-sm font-semibold">Why these requests are compatible</h3>
                  <ul className="mt-2 space-y-1.5 text-[12px] leading-5 text-muted">
                    {selectedGroup.included_reasons.map((reason) => (
                      <li key={reason} className="flex gap-1.5">
                        <Check size={13} className="mt-0.5 shrink-0 text-accent" aria-hidden /> {reason}
                      </li>
                    ))}
                  </ul>
                  <div className="mt-4 space-y-3">
                    <CapacityBar
                      label="Peak weight"
                      value={selectedGroup.max_load_weight_kg}
                      max={Number(selectedGroup.vehicle.max_weight_kg)}
                      unit="kg"
                    />
                    <CapacityBar
                      label="Peak volume"
                      value={selectedGroup.max_load_volume_m3}
                      max={Number(selectedGroup.vehicle.max_volume_m3)}
                      unit="m³"
                    />
                  </div>
                  <p className="mt-3 text-[11px] leading-4 text-muted">
                    Destinations preserved:{" "}
                    {selectedGroup.requests
                      .map((request) =>
                        request.type === "return"
                          ? request.authorized_hub ?? request.destination.label
                          : request.destination.label,
                      )
                      .join(" · ")}
                  </p>

                  <div className="mt-4 space-y-2 border-t pt-3">
                    <label className="label" htmlFor="offer-partner">
                      Offer to partner (optional)
                    </label>
                    <select
                      id="offer-partner"
                      className="input"
                      value={partnerId}
                      onChange={(event) => setPartnerId(event.target.value)}
                    >
                      <option value="">Create unassigned proposal</option>
                      {selectedGroup.partner_options.map((option) => (
                        <option key={option.partner_id} value={option.partner_id}>
                          {option.name} · {option.vehicle_type} · {option.max_weight_kg} kg
                        </option>
                      ))}
                    </select>
                    {selectedGroup.partner_options.length === 0 ? (
                      <p className="text-[11px] leading-4 text-muted">
                        No verified available partner fits this group. The proposal can still be created unassigned using
                        the configured reference vehicle.
                      </p>
                    ) : null}
                    <textarea
                      className="input min-h-[64px]"
                      placeholder="Dispatch note (optional)"
                      aria-label="Dispatch note"
                      value={note}
                      onChange={(event) => setNote(event.target.value)}
                    />
                    <button
                      type="button"
                      className="btn btn-primary w-full"
                      onClick={() => commit(selectedGroup)}
                      disabled={busy !== null}
                    >
                      {busy === "commit" ? <Loader2 size={16} className="animate-spin" aria-hidden /> : null}
                      Create proposed batch
                    </button>
                    <p className="text-center text-[10px] leading-4 text-muted">
                      Feasibility and reservations are revalidated atomically on commit.
                    </p>
                  </div>
                </div>
              ) : null}

              <div className="rounded-card border bg-surface p-4">
                <h3 className="flex items-center gap-2 text-sm font-semibold">
                  <X size={15} className="text-[#8c2f2f]" aria-hidden /> Rejections & near misses
                </h3>
                {result.near_misses.length === 0 && result.unmatched.length === 0 ? (
                  <p className="mt-2 text-[12px] text-muted">No rejections recorded in this run.</p>
                ) : (
                  <ul className="mt-2 space-y-2">
                    {result.near_misses.slice(0, 8).map((item, index) => (
                      <li key={`${item.reason_code}-${index}`} className="rounded-control bg-surface-muted px-3 py-2 text-[12px] leading-5">
                        <span className="chip chip-amber !px-1.5 !py-0.5 mr-1 text-[10px]">
                          {item.reason_code.replaceAll("_", " ")}
                        </span>
                        {item.message}
                      </li>
                    ))}
                    {result.unmatched.map((item) => (
                      <li key={item.code} className="rounded-control bg-surface-muted px-3 py-2 text-[12px] leading-5">
                        <span className="chip chip-neutral mr-1 !px-1.5 !py-0.5 text-[10px]">
                          {item.reason.replaceAll("_", " ")}
                        </span>
                        <span className="mono text-[10px]">{item.code}</span> {item.message}
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="rounded-card border bg-surface-muted p-4">
                <h3 className="text-sm font-semibold">Method disclosure</h3>
                <ul className="mt-2 space-y-1 text-[11px] leading-4 text-muted">
                  {result.assumptions.map((assumption) => (
                    <li key={assumption}>• {assumption}</li>
                  ))}
                  {result.routing_notes.map((noteItem) => (
                    <li key={noteItem}>• {noteItem}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {!result && !created ? (
        <div className="mt-4 flex items-start gap-2 rounded-control bg-surface-muted px-4 py-3 text-[12px] leading-5 text-muted">
          <AlertTriangle size={15} className="mt-0.5 shrink-0" aria-hidden />
          Preview reads real pending requests and computes a fresh route matrix. Nothing is reserved until a proposal is
          created, and a request can never be in two active batches.
        </div>
      ) : null}
    </section>
  );
}

export function GroupStatusChips({ group }: { group: PreviewGroup }) {
  return (
    <div className="flex flex-wrap gap-1">
      {group.requests.map((request) => (
        <StatusBadge key={request.id} status={request.status} />
      ))}
    </div>
  );
}
