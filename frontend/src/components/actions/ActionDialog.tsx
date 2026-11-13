"use client";

import { Loader2, X } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";

export default function ActionDialog({
  label,
  title,
  description,
  confirmLabel = "Confirm",
  tone = "primary",
  reasonRequired = false,
  reasonLabel = "Reason",
  reasonPlaceholder = "Explain what is happening so the audit trail is useful.",
  onConfirm,
  triggerClassName,
  disabled = false,
  icon,
  children,
}: {
  label: string;
  title: string;
  description?: string;
  confirmLabel?: string;
  tone?: "primary" | "danger" | "secondary";
  reasonRequired?: boolean;
  reasonLabel?: string;
  reasonPlaceholder?: string;
  onConfirm: (reason: string) => Promise<void>;
  triggerClassName?: string;
  disabled?: boolean;
  icon?: ReactNode;
  children?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    window.setTimeout(() => textareaRef.current?.focus(), 40);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, busy]);

  async function confirm() {
    if (reasonRequired && reason.trim().length < 5) {
      setError("Add a short reason (at least 5 characters).");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onConfirm(reason.trim());
      setOpen(false);
      setReason("");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "That action could not be completed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        type="button"
        className={cn("btn", tone === "danger" ? "btn-danger" : tone === "secondary" ? "btn-secondary" : "btn-primary", triggerClassName)}
        onClick={() => setOpen(true)}
        disabled={disabled}
      >
        {icon}
        {label}
      </button>
      {open ? (
        <div className="fixed inset-0 z-[100] flex items-end justify-center bg-ink/45 p-3 sm:items-center" role="presentation">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="action-dialog-title"
            className="w-full max-w-md rounded-modal border bg-surface p-5 shadow-floating sm:p-6"
          >
            <div className="flex items-start justify-between gap-3">
              <h2 id="action-dialog-title" className="text-lg font-bold">
                {title}
              </h2>
              <button
                type="button"
                className="btn btn-ghost !min-h-[32px] !px-2"
                onClick={() => setOpen(false)}
                aria-label="Close dialog"
                disabled={busy}
              >
                <X size={17} aria-hidden />
              </button>
            </div>
            {description ? <p className="mt-2 text-sm leading-6 text-muted">{description}</p> : null}
            <div className="mt-4 space-y-3">
              {children}
              {reasonRequired || reasonLabel !== "Reason" ? (
                <div>
                  <label className="label" htmlFor="action-reason">
                    {reasonLabel}
                  </label>
                  <textarea
                    id="action-reason"
                    ref={textareaRef}
                    className="input min-h-[88px]"
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                    placeholder={reasonPlaceholder}
                  />
                </div>
              ) : null}
              {error ? (
                <p className="rounded-control bg-red-soft px-3 py-2 text-[13px] text-[#8c2f2f]" role="alert">
                  {error}
                </p>
              ) : null}
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" className="btn btn-secondary" onClick={() => setOpen(false)} disabled={busy}>
                Cancel
              </button>
              <button
                type="button"
                className={cn("btn", tone === "danger" ? "btn-danger" : "btn-primary")}
                onClick={confirm}
                disabled={busy}
              >
                {busy ? <Loader2 size={15} className="animate-spin" aria-hidden /> : null}
                {confirmLabel}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
