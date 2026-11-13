"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Callout, Field } from "@/components/ui";
import { ApiError, apiPost } from "@/lib/api";

const CATEGORIES = [
  { value: "delivery_failure", label: "Delivery failure" },
  { value: "damaged_parcel", label: "Damaged parcel" },
  { value: "address_problem", label: "Address problem" },
  { value: "capacity_problem", label: "Capacity problem" },
  { value: "route_problem", label: "Route problem" },
  { value: "other", label: "Other" },
];

export default function IssueForm({
  requestId,
  compact = false,
}: {
  requestId: number;
  compact?: boolean;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(!compact);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function submit(formData: FormData) {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      await apiPost("/issues", {
        request_id: requestId,
        category: String(formData.get("category") ?? "other"),
        severity: String(formData.get("severity") ?? "medium"),
        description: String(formData.get("description") ?? ""),
      });
      setSuccess("Issue reported. An administrator will review it.");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not report the issue.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      {compact ? (
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => setOpen((value) => !value)}>
          {open ? "Hide issue form" : "Report an issue"}
        </button>
      ) : null}
      {open ? (
        <form action={submit} className="mt-3 space-y-3">
          {success ? <Callout tone="accent">{success}</Callout> : null}
          {error ? <Callout tone="danger">{error}</Callout> : null}
          <div className="field-grid">
            <Field label="Category" htmlFor="issue-category">
              <select id="issue-category" name="category" className="input">
                {CATEGORIES.map((category) => (
                  <option key={category.value} value={category.value}>
                    {category.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Severity" htmlFor="issue-severity">
              <select id="issue-severity" name="severity" className="input" defaultValue="medium">
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </Field>
          </div>
          <Field label="What happened?" htmlFor="issue-description" hint="At least 10 characters. Do not include payment details.">
            <textarea id="issue-description" name="description" className="input min-h-[96px]" required minLength={10} />
          </Field>
          <button type="submit" className="btn btn-secondary" disabled={busy}>
            {busy ? <Loader2 size={15} className="animate-spin" aria-hidden /> : null}
            Submit issue
          </button>
        </form>
      ) : null}
    </div>
  );
}
