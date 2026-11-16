"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button, ErrorText } from "@/components/ui-bits";
import { Callout, Card, Field, PageHeader } from "@/components/ui";
import { ApiError, apiGet, apiPatch } from "@/lib/api";

type Config = {
  effective: Record<string, number | string>;
  overrides: Record<string, number>;
  bounds: Record<string, { min: number; max: number }>;
  updated_at: string | null;
  disclaimer: string;
};

export default function AdminMatchingPage() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { data } = useQuery({ queryKey: ["admin-matching-config"], queryFn: () => apiGet<Config>("/admin/matching-config") });

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    const form = new FormData(event.currentTarget);
    const overrides: Record<string, number> = {};
    form.forEach((value, key) => {
      if (String(value).trim() !== "") overrides[key] = Number(value);
    });
    try {
      await apiPatch("/admin/matching-config", { overrides });
      await queryClient.invalidateQueries({ queryKey: ["admin-matching-config"] });
      setMessage("Matching configuration saved and active.");
    } catch (caught) {
      if (caught instanceof ApiError) setError(Object.values(caught.fields).join(" ") || caught.message);
      else setError("Configuration could not be saved.");
    } finally { setBusy(false); }
  }

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader eyebrow="Matching configuration" title="Tune the route-aware matcher" description="These bounds tune a deterministic insertion heuristic. They are not presented as universally optimal." />
      {error ? <ErrorText>{error}</ErrorText> : null}
      {message ? <p className="mb-4 rounded-control bg-accent-soft px-3 py-2 text-sm text-accent-strong">{message}</p> : null}
      {data ? (
        <form onSubmit={save} className="card card-pad space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            {Object.entries(data.effective).filter(([key]) => key in data.bounds).map(([key, value]) => (
              <Field key={key} label={`${key.replaceAll("_", " ")} (${data.bounds[key].min}–${data.bounds[key].max})`}>
                <input name={key} type="number" step="0.1" className="input" defaultValue={String(value)} />
              </Field>
            ))}
          </div>
          <Callout tone="info">{data.disclaimer}</Callout>
          <Button type="submit" busy={busy}>Save matching settings</Button>
          <p className="text-xs text-muted">Effective provider: {String(data.effective.provider ?? "auto")} · overrides take effect immediately for new plans and scans.</p>
        </form>
      ) : <p className="text-sm text-muted">Loading configuration…</p>}
    </div>
  );
}
