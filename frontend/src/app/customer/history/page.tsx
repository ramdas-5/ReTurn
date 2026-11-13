import Link from "next/link";

import RequestTable from "@/components/RequestTable";
import { PageHeader } from "@/components/ui";
import { requireUser, serverFetchList } from "@/lib/server";
import type { DeliveryRequest } from "@/lib/types";

export const metadata = { title: "Request history" };

export default async function CustomerHistoryPage() {
  await requireUser("customer");
  const { data: requests } = await serverFetchList<DeliveryRequest>(
    "/requests?status=completed,cancelled,failed&per_page=100",
  );

  return (
    <div>
      <PageHeader
        eyebrow="Archive"
        title="Request history"
        description="Completed, cancelled and failed requests. Tracking history is preserved even when a request is cancelled."
        actions={
          <Link href="/customer/requests" className="btn btn-secondary">
            Back to active requests
          </Link>
        }
      />
      <RequestTable
        requests={requests}
        emptyMessage="No historical requests yet. Completed and cancelled requests will appear here."
      />
    </div>
  );
}
