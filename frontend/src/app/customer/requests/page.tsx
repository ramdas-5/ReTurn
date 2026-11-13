import { Search } from "lucide-react";
import Link from "next/link";

import RequestTable from "@/components/RequestTable";
import { PageHeader, StatCard } from "@/components/ui";
import { requireUser, serverFetchList } from "@/lib/server";
import type { DeliveryRequest } from "@/lib/types";

export const metadata = { title: "My requests" };

const STATUS_OPTIONS = [
  { value: "", label: "All states" },
  { value: "pending_matching", label: "Pending match" },
  { value: "batched", label: "In proposed batch" },
  { value: "assigned", label: "Partner accepted" },
  { value: "in_progress", label: "On route" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
  { value: "failed", label: "Failed" },
];

export default async function CustomerRequestsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; status?: string; type?: string }>;
}) {
  await requireUser("customer");
  const params = await searchParams;
  const query = new URLSearchParams({ per_page: "50" });
  if (params.q) query.set("q", params.q);
  if (params.status) query.set("status", params.status);
  if (params.type) query.set("type", params.type);
  const { data: requests } = await serverFetchList<DeliveryRequest>(`/requests?${query.toString()}`);

  const activeCount = requests.filter((request) =>
    ["pending_matching", "batched", "assigned", "in_progress"].includes(request.status),
  ).length;
  const deliveredCount = requests.filter((request) => request.status === "completed").length;

  return (
    <div>
      <PageHeader
        eyebrow="Request register"
        title="My requests"
        description="Search your own requests and see the exact next step. Statuses come from the API; nothing here is a mock."
        actions={
          <>
            <Link href="/customer/returns/new" className="btn btn-primary">Return a product</Link>
            <Link href="/customer/parcels/new" className="btn btn-secondary">Send a parcel</Link>
          </>
        }
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <StatCard label="Matching the filter" value={requests.length} hint="Up to 50 most recent" />
        <StatCard label="Active" value={activeCount} hint="Including proposed batches" tone="accent" />
        <StatCard label="Delivered" value={deliveredCount} hint="Completed requests" tone="blue" />
      </div>

      <form className="card card-pad mb-5 flex flex-col gap-3 lg:flex-row lg:items-end" method="get">
        <div className="flex-1">
          <label className="label" htmlFor="request-search">Search</label>
          <div className="relative">
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" aria-hidden />
            <input
              id="request-search"
              name="q"
              defaultValue={params.q ?? ""}
              className="input pl-9"
              placeholder="Code, parcel, area…"
            />
          </div>
        </div>
        <div className="w-full lg:w-52">
          <label className="label" htmlFor="request-status">Status</label>
          <select id="request-status" name="status" className="input" defaultValue={params.status ?? ""}>
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </div>
        <div className="w-full lg:w-44">
          <label className="label" htmlFor="request-type">Service</label>
          <select id="request-type" name="type" className="input" defaultValue={params.type ?? ""}>
            <option value="">Both services</option>
            <option value="return">Product return</option>
            <option value="parcel">Parcel delivery</option>
          </select>
        </div>
        <button type="submit" className="btn btn-primary">Apply filters</button>
        <Link href="/customer/requests" className="btn btn-ghost">Clear</Link>
      </form>

      <RequestTable
        requests={requests}
        emptyMessage="No requests match these filters. Try clearing them, or create a return or parcel."
      />
    </div>
  );
}
