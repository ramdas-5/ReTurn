import Link from "next/link";

import { EmptyState } from "@/components/ui";
import { ServiceBadge, StatusBadge } from "@/components/Status";
import { formatDateTime, formatWindow } from "@/lib/format";
import type { OrderSummary } from "@/lib/types";

export default function OrderList({
  orders,
  hrefBase,
  showConsumer = false,
  emptyTitle = "No orders yet",
  emptyDescription = "Orders will appear here as soon as they are created.",
}: {
  orders: OrderSummary[];
  hrefBase: string;
  showConsumer?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
}) {
  if (!orders.length) {
    return <EmptyState title={emptyTitle} description={emptyDescription} />;
  }
  return (
    <div className="table-wrap">
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Order</th>
              <th>Route</th>
              <th>Pickup window</th>
              <th>Status</th>
              <th>Deadline</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((order) => (
              <tr key={order.id}>
                <td>
                  <Link href={`${hrefBase}/${order.id}`} className="font-semibold text-accent hover:underline">
                    {order.order_number}
                  </Link>
                  <div className="mt-1 flex flex-wrap items-center gap-1.5">
                    <ServiceBadge type={order.service_type} />
                    {order.is_demo ? <span className="chip chip-neutral">demo</span> : null}
                  </div>
                  {showConsumer && order.consumer ? (
                    <p className="mt-1 text-xs text-muted">{order.consumer.full_name}</p>
                  ) : null}
                </td>
                <td>
                  <p className="text-[13px] font-medium">{order.pickup.area ?? "—"}</p>
                  <p className="text-xs text-muted">→ {order.delivery.area ?? "—"}</p>
                </td>
                <td className="text-[13px]">{formatWindow(order.pickup.window_start, order.pickup.window_end)}</td>
                <td><StatusBadge status={order.status} /></td>
                <td className="text-[13px]">{formatDateTime(order.delivery.deadline)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
