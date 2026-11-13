import Link from "next/link";

import { ServiceBadge, StatusBadge } from "@/components/Status";
import { destinationLabel, formatDateTime, formatWeight } from "@/lib/format";
import type { DeliveryRequest } from "@/lib/types";

export default function RequestTable({
  requests,
  detailBase = "/customer/requests",
  showCustomer = false,
  emptyMessage = "No requests match this view yet.",
}: {
  requests: DeliveryRequest[];
  detailBase?: string;
  showCustomer?: boolean;
  emptyMessage?: string;
}) {
  if (requests.length === 0) {
    return (
      <div className="rounded-card border border-dashed bg-surface px-5 py-10 text-center text-sm text-muted">
        {emptyMessage}
      </div>
    );
  }

  return (
    <>
      <div className="table-wrap hidden md:block">
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Request</th>
                {showCustomer ? <th scope="col">Customer</th> : null}
                <th scope="col">Journey</th>
                <th scope="col">Schedule</th>
                <th scope="col">Status</th>
                <th scope="col">
                  <span className="sr-only">Open</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {requests.map((request) => (
                <tr key={request.id}>
                  <td>
                    <div className="flex flex-wrap items-center gap-1.5">
                      <Link href={`${detailBase}/${request.id}`} className="link mono text-[12px] font-medium">
                        {request.code}
                      </Link>
                      <ServiceBadge type={request.type} />
                    </div>
                    <p className="mt-1 max-w-[220px] truncate text-[12px] text-muted">{request.parcel.description}</p>
                    <p className="text-[11px] text-muted">{formatWeight(request.parcel.weight_kg)} · {request.parcel.size_class}</p>
                  </td>
                  {showCustomer ? (
                    <td>
                      <p className="text-[13px] font-medium">{request.customer?.name ?? "—"}</p>
                      <p className="text-[11px] text-muted">{request.pickup.area}</p>
                    </td>
                  ) : null}
                  <td>
                    <p className="text-[13px] font-medium">{request.pickup.area}</p>
                    <p className="max-w-[220px] text-[12px] leading-5 text-muted">→ {destinationLabel(request)}</p>
                  </td>
                  <td>
                    <p className="text-[12px] font-medium">{formatDateTime(request.pickup_window_start)}</p>
                    <p className="text-[11px] leading-5 text-muted">
                      Window closes {formatDateTime(request.pickup_window_end)}
                    </p>
                    <p className="text-[11px] leading-5 text-muted">
                      Deadline {formatDateTime(request.delivery_deadline)}
                    </p>
                  </td>
                  <td className="max-w-[220px]">
                    <StatusBadge status={request.status} />
                    <p className="mt-1.5 text-[11px] leading-4 text-muted">{request.next_step}</p>
                  </td>
                  <td className="text-right">
                    <Link href={`${detailBase}/${request.id}`} className="btn btn-secondary btn-sm whitespace-nowrap">
                      View details
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <ul className="space-y-3 md:hidden">
        {requests.map((request) => (
          <li key={request.id} className="card p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="mono text-[12px] font-medium">{request.code}</span>
              <StatusBadge status={request.status} />
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <ServiceBadge type={request.type} />
              <span className="text-[12px] text-muted">{request.parcel.description}</span>
            </div>
            {showCustomer ? <p className="mt-2 text-[12px] text-muted">{request.customer?.name}</p> : null}
            <p className="mt-2 text-[13px]">
              <span className="font-medium">{request.pickup.area}</span>
              <span className="text-muted"> → {destinationLabel(request)}</span>
            </p>
            <p className="mt-1 text-[11px] leading-5 text-muted">
              Pickup {formatDateTime(request.pickup_window_start)} — {formatDateTime(request.pickup_window_end)}
            </p>
            <p className="mt-1 text-[11px] leading-5 text-muted">{request.next_step}</p>
            <Link href={`${detailBase}/${request.id}`} className="btn btn-secondary btn-sm mt-3 w-full">
              View details
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}
