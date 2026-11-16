"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { MapPin, Play, Square, Wifi } from "lucide-react";
import { useState } from "react";

import { Button, ErrorText } from "@/components/ui-bits";
import { Card } from "@/components/ui";
import { ApiError, apiGet, apiPost } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

type DutyPayload = {
  duty: {
    id: number;
    status: string;
    status_label: string;
    started_at: string;
    last_heartbeat_at: string;
  } | null;
  is_live: boolean;
  verification_status: string;
  heartbeat_timeout_minutes: number;
  recent_sessions: Array<{ id: number; status: string; started_at: string; ended_at: string | null }>;
};

export default function DriverDutyControls({ compact = false }: { compact?: boolean }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const { data } = useQuery({
    queryKey: ["driver-duty"],
    queryFn: () => apiGet<DutyPayload>("/driver/duty"),
  });

  const duty = data?.duty ?? null;

  async function call(key: string, path: string, body: unknown = {}) {
    setBusy(key);
    setError(null);
    setMessage(null);
    try {
      await apiPost(path, body);
      await queryClient.invalidateQueries({ queryKey: ["driver-duty"] });
      await queryClient.invalidateQueries({ queryKey: ["driver-summary"] });
      setMessage("Updated.");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Action failed.");
    } finally {
      setBusy(null);
    }
  }

  async function start(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await call("start", "/driver/duty/start", {
      status: form.get("status"),
      device_label: form.get("device_label"),
      latitude: Number(form.get("latitude")),
      longitude: Number(form.get("longitude")),
    });
  }

  async function share(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await call("location", "/driver/location", {
      consent_granted: true,
      latitude: Number(form.get("latitude")),
      longitude: Number(form.get("longitude")),
      accuracy_m: Number(form.get("accuracy_m") || 15),
    });
  }

  return (
    <Card className={compact ? "" : "card-pad"}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="section-title">Duty & location</h2>
        <span className={`chip ${duty ? "chip-green" : "chip-neutral"}`}>{duty ? duty.status_label : "Off duty"}</span>
      </div>
      {error ? <div className="mt-3"><ErrorText>{error}</ErrorText></div> : null}
      {message ? <p className="mt-3 text-sm text-accent-strong">{message}</p> : null}

      {!duty ? (
        <form onSubmit={start} className="mt-4 space-y-3">
          <p className="text-sm text-muted">Go on duty to receive assignments. Location is optional and only used while on duty.</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <select name="status" className="input" defaultValue="available">
              <option value="available">Available</option>
              <option value="on_duty">On duty</option>
            </select>
            <input name="device_label" className="input" placeholder="Device label (optional)" />
            <input name="latitude" type="number" step="0.000001" className="input" placeholder="Latitude (optional)" />
            <input name="longitude" type="number" step="0.000001" className="input" placeholder="Longitude (optional)" />
          </div>
          <Button type="submit" busy={busy === "start"}><Play size={15} aria-hidden /> Start duty</Button>
        </form>
      ) : (
        <div className="mt-4 space-y-4">
          <p className="text-xs text-muted">Started {formatDateTime(duty.started_at)} · heartbeat {formatDateTime(duty.last_heartbeat_at)} · timeout {data?.heartbeat_timeout_minutes} min</p>
          <div className="flex flex-wrap gap-2">
            {["available", "busy", "on_break"].map((status) => (
              <button
                key={status}
                className={`btn btn-sm ${duty.status === status ? "btn-primary" : "btn-secondary"}`}
                disabled={busy === status}
                onClick={() => call(status, "/driver/duty/status", { status })}
              >
                {status.replaceAll("_", " ")}
              </button>
            ))}
            <button className="btn btn-secondary btn-sm" disabled={busy === "heartbeat"} onClick={() => call("heartbeat", "/driver/duty/heartbeat")}>
              <Wifi size={14} aria-hidden /> Heartbeat
            </button>
            <button className="btn btn-danger btn-sm" disabled={busy === "end"} onClick={() => call("end", "/driver/duty/end", { reason: "End of shift" })}>
              <Square size={14} aria-hidden /> End duty
            </button>
          </div>
          <form onSubmit={share} className="rounded-control border bg-surface-muted p-3">
            <p className="text-sm font-medium flex items-center gap-1.5"><MapPin size={14} aria-hidden /> Share a location update</p>
            <p className="mt-1 text-xs text-muted">Only while on duty and with your explicit consent. The platform does not track you off duty.</p>
            <div className="mt-2 grid gap-2 sm:grid-cols-3">
              <input name="latitude" type="number" step="0.000001" className="input" placeholder="Latitude" required />
              <input name="longitude" type="number" step="0.000001" className="input" placeholder="Longitude" required />
              <Button type="submit" busy={busy === "location"} className="btn btn-secondary">Share location</Button>
            </div>
          </form>
        </div>
      )}
    </Card>
  );
}
