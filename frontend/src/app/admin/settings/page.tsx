"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button, ErrorText } from "@/components/ui-bits";
import { Card, Field, PageHeader } from "@/components/ui";
import { ApiError, apiGet, apiPatch } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

type Setting = { key: string; value: unknown; description: string | null; updated_at: string | null };

export default function AdminSettingsPage() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const { data } = useQuery({ queryKey: ["admin-settings"], queryFn: () => apiGet<Setting[]>("/admin/settings") });

  async function save(key: string, event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const raw = String(new FormData(event.currentTarget).get("value") ?? "");
    let parsed: unknown;
    try { parsed = JSON.parse(raw); } catch { setError("That value is not valid JSON."); return; }
    setBusy(key);
    setError(null);
    setMessage(null);
    try {
      await apiPatch(`/admin/settings/${encodeURIComponent(key)}`, { value: parsed });
      setMessage(`Setting ${key} saved.`);
      await queryClient.invalidateQueries({ queryKey: ["admin-settings"] });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Setting could not be saved.");
    } finally { setBusy(null); }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader eyebrow="Platform settings" title="Stored configuration" description="Settings are audited JSON values. Matching thresholds have a dedicated editor; other keys are managed here." />
      {error ? <ErrorText>{error}</ErrorText> : null}
      {message ? <p className="mb-4 rounded-control bg-accent-soft px-3 py-2 text-sm text-accent-strong">{message}</p> : null}
      <div className="space-y-4">
        {data?.map((setting) => (
          <form key={setting.key} onSubmit={(event) => save(setting.key, event)} className="card card-pad space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="mono text-sm font-semibold">{setting.key}</p>
              <span className="text-xs text-muted">{formatDateTime(setting.updated_at)}</span>
            </div>
            {setting.description ? <p className="text-xs text-muted">{setting.description}</p> : null}
            <Field label="JSON value"><textarea name="value" rows={3} className="input mono" defaultValue={JSON.stringify(setting.value, null, 2)} /></Field>
            <Button type="submit" busy={busy === setting.key} className="btn btn-secondary btn-sm">Save value</Button>
          </form>
        ))}
        {data && data.length === 0 ? <Card><p className="text-sm text-muted">No platform settings have been stored yet. Use the matching configuration page to create matching defaults.</p></Card> : null}
      </div>
    </div>
  );
}
