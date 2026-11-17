"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCheck } from "lucide-react";

import { PageHeader } from "@/components/ui";
import { apiGetList, apiPost } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { AppNotification } from "@/lib/types";

export default function ConsumerNotificationsPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["notifications-page"],
    queryFn: () => apiGetList<AppNotification>("/notifications?limit=50"),
  });

  async function markAll() {
    await apiPost("/notifications/read-all");
    await queryClient.invalidateQueries({ queryKey: ["notifications-page"] });
    await queryClient.invalidateQueries({ queryKey: ["notifications"] });
  }

  async function markOne(id: number) {
    await apiPost(`/notifications/${id}/read`);
    await queryClient.invalidateQueries({ queryKey: ["notifications-page"] });
    await queryClient.invalidateQueries({ queryKey: ["notifications"] });
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader eyebrow="Notifications" title="Updates about your orders" description="Status changes, proof events and manager decisions." actions={<button className="btn btn-secondary btn-sm" onClick={markAll}><CheckCheck size={14} aria-hidden /> Mark all read</button>} />
      {isLoading ? <p className="text-sm text-muted">Loading notifications…</p> : null}
      <div className="space-y-2">
        {data?.data.map((item) => (
          <article key={item.id} className={`panel rounded-card border p-4 ${item.read_at ? "" : "border-danger"}`}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold">{item.title}</p>
                <p className="mt-1 text-sm leading-6 text-muted">{item.body}</p>
                <p className="mt-1 text-2xs text-muted">{formatDateTime(item.created_at)}</p>
              </div>
              {!item.read_at ? <button className="btn btn-ghost btn-sm" onClick={() => markOne(item.id)}>Mark read</button> : null}
            </div>
          </article>
        ))}
        {data && data.data.length === 0 ? <p className="text-sm text-muted">No notifications have been sent yet.</p> : null}
      </div>
    </div>
  );
}
