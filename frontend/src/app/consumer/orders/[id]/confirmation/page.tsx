"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { StatusBadge } from "@/components/Status";
import { Card, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatWindow } from "@/lib/format";
import type { OrderDetail } from "@/lib/types";

export default function ConfirmationPage() {
  const params = useParams<{ id: string }>();
  const { data, error } = useQuery({
    queryKey: ["consumer-order", params.id],
    queryFn: () => apiGet<OrderDetail>(`/orders/${params.id}`),
  });

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader eyebrow="Order received" title="Your request is with the operations team" description="No driver is committed yet. A manager will review feasibility and assign compatible work." />
      {error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-[#8c2f2f]">{(error as Error).message}</p> : null}
      {data ? (
        <Card className="card-pad">
          <div className="flex items-start gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-full bg-accent-soft text-accent-strong"><CheckCircle2 size={22} aria-hidden /></span>
            <div>
              <p className="text-lg font-bold">{data.order_number}</p>
              <StatusBadge status={data.status} className="mt-2" />
            </div>
          </div>
          <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2">
            <div><dt className="text-xs uppercase tracking-wide text-muted">Pickup</dt><dd>{data.pickup_address?.address_line}, {data.pickup_address?.area}</dd></div>
            <div><dt className="text-xs uppercase tracking-wide text-muted">Destination</dt><dd>{data.delivery_address?.address_line}, {data.delivery_address?.area}</dd></div>
            <div className="sm:col-span-2"><dt className="text-xs uppercase tracking-wide text-muted">Pickup window</dt><dd>{formatWindow(data.pickup.window_start, data.pickup.window_end)}</dd></div>
          </dl>
          <div className="mt-6 flex flex-wrap gap-2">
            <Link href={`/consumer/orders/${data.id}`} className="btn btn-primary">View order details</Link>
            <Link href="/consumer/orders" className="btn btn-secondary">All orders</Link>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
