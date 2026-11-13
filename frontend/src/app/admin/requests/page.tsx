import { AlertTriangle, Search, Sparkles } from "lucide-react";
import Link from "next/link";

import CancelRequestButton from "@/components/actions/CancelRequestButton";
import { ServiceBadge, StatusBadge } from "@/components/Status";
import Timeline from "@/components/Timeline";
import { Callout, Card, EmptyState, PageHeader, StatCard } from "@/components/ui";
import {
  destinationLabel,
  formatDateTime,
  formatVolume,
  formatWeight,
  serviceLabel,
} from "@/lib/format";
import { requireUser, serverFetch, serverFetchList } from "@/lib/server";
import type { DeliveryRequest } from "@/lib/types";

export const metadata = { title: "Request queue" };

export default async function AdminRequestsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; status?: string; type?: string; request?: string }>;
}) {
  await requireUser("admin");
  const params = await searchParams;
  const query = new URLSearchParams({ per_page: "100" });
  if (params.q) query.set("q", params.q);
  if (params.status) query.set("status", params.status);
  if (params.type) query.set("type", params.type);
  const { data: requests } = await serverFetchList<DeliveryRequest>(`/requests?${query.toString()}`);

  const selectedId = params.request ? Number(params.request) : requests[0]?.id;
  let selected: DeliveryRequest | null = null;
  if (selectedId) {
    try {
      selected = await serverFetch<DeliveryRequest>(`/requests/${selectedId}`);
    } catch {
      selected = null;
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Operations queue"
        title="All requests"
        description="Inspect any request, its parcel-level history, contact details and batch reservation. Creating or changing a batch stays in the matching console."
        actions={
          <Link href="/admin/batches#matching" className="btn btn-primary">
            <Sparkles size={16} aria-hidden /> Run matching
          </Link>
        }
      />

      <div className="mb-5 grid gap-4 sm:grid-cols-3">
        <StatCard label="Requests in view" value={requests.length} hint="Filtered, up to 100" />
        <StatCard
          label="Awaiting matching"
          value={requests.filter((request) => request.status === "pending_matching").length}
          hint="Eligible for a future run"
          tone="accent"
        />
        <StatCard
          label="In active batches"
          value={requests.filter((request) => ["batched", "assigned", "in_progress"].includes(request.status)).length}
          hint="Reserved or executing"
          tone="blue"
        />
      </div>

      <form className="card card-pad mb-5 flex flex-col gap-3 lg:flex-row lg:items-end" method="get">
        <div className="flex-1">
          <label className="label" htmlFor="admin-request-search">Search</label>
          <div className="relative">
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" aria-hidden />
            <input
              id="admin-request-search"
              name="q"
              defaultValue={params.q ?? ""}
              className="input pl-9"
              placeholder="Code, customer, parcel, area…"
            />
          </div>
        </div>
        <div className="w-full lg:w-48">
          <label className="label" htmlFor="admin-request-status">Status</label>
          <select id="admin-request-status" name="status" className="input" defaultValue={params.status ?? ""}>
            <option value="">All states</option>
            <option value="pending_matching">Pending match</option>
            <option value="batched">In proposed batch</option>
            <option value="assigned">Partner accepted</option>
            <option value="in_progress">On route</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
            <option value="failed">Failed</option>
          </select>
        </div>
        <div className="w-full lg:w-44">
          <label className="label" htmlFor="admin-request-type">Service</label>
          <select id="admin-request-type" name="type" className="input" defaultValue={params.type ?? ""}>
            <option value="">Both</option>
            <option value="return">Return</option>
            <option value="parcel">Parcel</option>
          </select>
        </div>
        <button type="submit" className="btn btn-primary">Filter</button>
        <Link href="/admin/requests" className="btn btn-ghost">Clear</Link>
      </form>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <Card className="overflow-hidden">
          <div className="border-b px-4 py-3">
            <h2 className="text-sm font-semibold">Request register</h2>
          </div>
          {requests.length === 0 ? (
            <div className="p-4">
              <EmptyState title="No requests match" description="Clear the filters or wait for customers to submit a request." />
            </div>
          ) : (
            <ul className="max-h-[720px] divide-y overflow-y-auto">
              {requests.map((request) => (
                <li key={request.id}>
                  <Link
                    href={`/admin/requests?request=${request.id}${params.q ? `&q=${encodeURIComponent(params.q)}` : ""}`}
                    className={`block px-4 py-3 transition hover:bg-surface-muted ${
                      selectedId === request.id ? "bg-accent-soft/50" : ""
                    }`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="mono text-[12px] font-medium">{request.code}</span>
                        <ServiceBadge type={request.type} />
                      </div>
                      <StatusBadge status={request.status} />
                    </div>
                    <p className="mt-1 text-[12px]">
                      <span className="font-medium">{request.customer?.name}</span>{" "}
                      <span className="text-muted">· {request.pickup.area} → {destinationLabel(request)}</span>
                    </p>
                    <p className="text-[11px] text-muted">
                      {formatDateTime(request.created_at)} · {formatWeight(request.parcel.weight_kg)} ·{" "}
                      {request.parcel.handling.length ? request.parcel.handling.join(", ") : "standard handling"}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <div className="space-y-5 xl:sticky xl:top-24 xl:self-start">
          {selected ? (
            <>
              <Card className="card-pad">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="mono text-[12px] font-semibold">{selected.code}</span>
                      <ServiceBadge type={selected.type} />
                      <StatusBadge status={selected.status} />
                    </div>
                    <h2 className="mt-2 text-lg font-bold">{serviceLabel(selected.type)}</h2>
                    <p className="mt-1 text-[12px] leading-5 text-muted">{selected.next_step}</p>
                  </div>
                  {["pending_matching", "batched"].includes(selected.status) ? (
                    <CancelRequestButton requestId={selected.id} code={selected.code} />
                  ) : null}
                </div>

                <dl className="mt-4 grid gap-3 border-t pt-4 text-[12px] sm:grid-cols-2">
                  <div>
                    <dt className="text-[10px] uppercase tracking-wide text-muted">Customer</dt>
                    <dd className="mt-0.5 font-medium">{selected.customer?.name}</dd>
                    <dd className="text-muted">{selected.customer?.email} · {selected.customer?.phone ?? "no phone"}</dd>
                  </div>
                  <div>
                    <dt className="text-[10px] uppercase tracking-wide text-muted">Pickup window</dt>
                    <dd className="mt-0.5">{formatDateTime(selected.pickup_window_start)}</dd>
                    <dd className="text-muted">closes {formatDateTime(selected.pickup_window_end)}</dd>
                  </div>
                  <div>
                    <dt className="text-[10px] uppercase tracking-wide text-muted">Pickup</dt>
                    <dd className="mt-0.5">{selected.pickup.label}</dd>
                    <dd className="text-muted">{selected.pickup.address_line}</dd>
                  </div>
                  <div>
                    <dt className="text-[10px] uppercase tracking-wide text-muted">
                      {selected.type === "return" ? "Authorised return destination" : "Recipient address"}
                    </dt>
                    <dd className="mt-0.5">
                      {selected.type === "return"
                        ? selected.return_detail?.authorized_hub_name
                        : `${selected.recipient?.name} · ${selected.destination.label}`}
                    </dd>
                    <dd className="text-muted">{selected.destination.address_line}</dd>
                  </div>
                  <div>
                    <dt className="text-[10px] uppercase tracking-wide text-muted">Parcel</dt>
                    <dd className="mt-0.5">{selected.parcel.description}</dd>
                    <dd className="text-muted">
                      {formatWeight(selected.parcel.weight_kg)} · {formatVolume(selected.parcel.volume_m3)} ·{" "}
                      {selected.parcel.size_class}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[10px] uppercase tracking-wide text-muted">Deadline</dt>
                    <dd className="mt-0.5">{formatDateTime(selected.delivery_deadline)}</dd>
                    <dd className="mono text-[11px] text-muted">{selected.parcel.tracking_number}</dd>
                  </div>
                </dl>

                {selected.status === "pending_matching" ? (
                  <div className="mt-4">
                    <Callout tone="info" title="Why hasn't it matched?">
                      Rejection reasons are produced per matching run, not stored on the request. Open the{" "}
                      <Link href="/admin/batches#matching" className="link">matching console</Link> to see live
                      feasibility explanations for this queue.
                    </Callout>
                  </div>
                ) : null}
                {selected.type === "return" && selected.return_detail?.return_reference ? (
                  <p className="mt-3 text-[12px] text-muted">
                    Return reference: <span className="mono">{selected.return_detail.return_reference}</span>
                    {selected.return_detail.retailer ? ` · ${selected.return_detail.retailer}` : ""}
                  </p>
                ) : null}
                {selected.notes ? <p className="mt-2 text-[12px] text-muted">Customer note: {selected.notes}</p> : null}
              </Card>

              <Card className="card-pad">
                <h2 className="section-title">Batch context</h2>
                {selected.batch_detail ? (
                  <div className="mt-2 space-y-2 text-[12px]">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="mono font-medium">{selected.batch_detail.code}</span>
                      <StatusBadge status={selected.batch_detail.status} />
                    </div>
                    <p className="text-muted">
                      {selected.batch_detail.requests.length} requests · estimated{" "}
                      {selected.batch_detail.savings_percent.toFixed(1)}% saving ·{" "}
                      {selected.batch_detail.partner?.name ?? "unassigned"}
                    </p>
                    <Link href={`/admin/batches?batch=${selected.batch_detail.id}`} className="btn btn-secondary btn-sm w-full">
                      Open batch
                    </Link>
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-muted">Not reserved in an active batch.</p>
                )}
              </Card>

              <Card className="card-pad">
                <h2 className="section-title">Parcel timeline</h2>
                <div className="mt-4">
                  <Timeline events={selected.tracking ?? []} />
                </div>
              </Card>
            </>
          ) : (
            <EmptyState
              icon={<AlertTriangle size={19} aria-hidden />}
              title="Select a request"
              description="Choose a request from the register to inspect its parcel journey, contacts and batch reservation."
            />
          )}
        </div>
      </div>
    </div>
  );
}
