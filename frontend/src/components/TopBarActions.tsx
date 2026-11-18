"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, CheckCheck, LogOut } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { apiGetList, apiPost } from "@/lib/api";
import { initials, relativeTime } from "@/lib/format";
import type { ApiUser, AppNotification } from "@/lib/types";

export function NotificationMenu() {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();
  const { data, isError } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => apiGetList<AppNotification>("/notifications?limit=10"),
    refetchInterval: 60_000,
  });
  const markAll = useMutation({
    mutationFn: () => apiPost<{ marked_read: number }>("/notifications/read-all"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });

  useEffect(() => {
    function onClick(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const unread = data?.meta?.unread_count ?? 0;
  const items = data?.data ?? [];

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        className="btn btn-ghost relative !min-h-[40px] !px-2.5"
        aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Bell size={19} aria-hidden />
        {unread > 0 ? (
          <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red px-1 text-2xs font-semibold text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        ) : null}
      </button>
      {open ? (
        <div className="panel absolute right-0 top-12 z-50 w-[330px] max-w-[calc(100vw-2rem)] overflow-hidden rounded-card border shadow-floating">
          <div className="flex items-center justify-between border-b px-4 py-3">
            <p className="text-sm font-semibold">Notifications</p>
            <button
              type="button"
              className="inline-flex items-center gap-1 text-xs text-accent-strong hover:underline disabled:opacity-50"
              onClick={() => markAll.mutate()}
              disabled={markAll.isPending || unread === 0}
            >
              <CheckCheck size={13} aria-hidden /> Mark all read
            </button>
          </div>
          <div className="max-h-[360px] overflow-y-auto">
            {isError ? (
              <p className="px-4 py-6 text-sm text-muted">Notifications are unavailable right now.</p>
            ) : items.length === 0 ? (
              <p className="px-4 py-6 text-sm text-muted">No notifications yet.</p>
            ) : (
              items.map((item) => (
                <Link
                  key={item.id}
                  href={item.link ?? "/"}
                  onClick={() => {
                    if (!item.read_at) {
                      void apiPost(`/notifications/${item.id}/read`).then(() =>
                        queryClient.invalidateQueries({ queryKey: ["notifications"] }),
                      );
                    }
                    setOpen(false);
                  }}
                  className="block border-b px-4 py-3 last:border-0 hover:bg-surface-tint"
                >
                  <div className="flex items-start gap-2">
                    <span
                      className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${
                        item.read_at ? "bg-transparent" : "bg-accent"
                      }`}
                      aria-label={item.read_at ? undefined : "Unread"}
                    />
                    <div>
                      <p className="text-sm font-medium leading-5">{item.title}</p>
                      <p className="mt-0.5 text-xs leading-5 text-muted">{item.body}</p>
                      <p className="mt-1 text-2xs uppercase tracking-wide text-muted">
                        {relativeTime(item.created_at)}
                      </p>
                    </div>
                  </div>
                </Link>
              ))
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function TopBarUser({ user }: { user: ApiUser }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function signOut() {
    setBusy(true);
    try {
      await apiPost("/auth/logout");
      router.push("/");
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center gap-2">
      <div className="hidden text-right sm:block">
        <p className="text-sm font-semibold leading-4">{user.full_name}</p>
        <p className="text-2xs capitalize leading-4 text-muted">{user.role}</p>
      </div>
      <div
        className="flex h-9 w-9 items-center justify-center rounded-full bg-accent-soft text-xs font-bold text-accent-strong"
        aria-hidden="true"
      >
        {initials(user.full_name)}
      </div>
      <button
        type="button"
        onClick={signOut}
        disabled={busy}
        className="btn btn-ghost !min-h-[40px] !px-2.5"
        aria-label="Sign out"
        title="Sign out"
      >
        <LogOut size={18} aria-hidden />
      </button>
    </div>
  );
}
