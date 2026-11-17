"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCheck } from "lucide-react";

import { PageHeader } from "@/components/ui";
import { apiGetList, apiPost } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { AppNotification } from "@/lib/types";

export default function DriverNotificationsPage() {
  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: ["driver-notifications"],
    queryFn: () => apiGetList<AppNotification>("/notifications?limit=50"),
  });

  async function markAll() {
    await apiPost("/notifications/read-all");
    await queryClient.invalidateQueries({ queryKey: ["driver-notifications"] });
    await queryClient.invalidateQueries({ queryKey: ["notifications"] });
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader eyebrow="Notifications" title="Dispatch updates" description="Batch assignments, route changes and status events." actions={<button className="btn btn-secondary btn-sm" onClick={markAll}><CheckCheck size={14} aria-hidden /> Mark all read</button>} />
      <div className="space-y-2">
        {data?.data.map((item) => (
          <article key={item.id} className={`panel rounded-card border p-4 ${item.read_at ? "" : "border-danger"}`}>
            <p className="text-sm font-semibold">{item.title}</p>
            <p className="mt-1 text-sm text-muted">{item.body}</p>
            <p className="mt-1 text-2xs text-muted">{formatDateTime(item.created_at)}</p>
          </article>
        ))}
        {data && data.data.length === 0 ? <p className="text-sm text-muted">No notifications yet.</p> : null}
      </div>
    </div>
  );
}
