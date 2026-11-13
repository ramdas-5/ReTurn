import { ArrowLeftRight } from "lucide-react";

import RequestForm from "@/components/forms/RequestForm";
import { PageHeader } from "@/components/ui";
import { requireUser } from "@/lib/server";

export const metadata = { title: "Return a product" };

export default async function NewReturnPage() {
  await requireUser("customer");
  const now = Date.now();
  const defaults = {
    start: new Date(now + 90 * 60 * 1000).toISOString(),
    end: new Date(now + 180 * 60 * 1000).toISOString(),
    deadline: new Date(now + 300 * 60 * 1000).toISOString(),
  };

  return (
    <div>
      <PageHeader
        back={{ href: "/customer", label: "Customer overview" }}
        eyebrow="Return lane"
        title="Return a product"
        description="Tell us where the parcel should be collected and which authorised return destination it belongs to. ReTurn checks compatibility after submission; a shared route is never assumed."
        actions={
          <span className="chip chip-teal">
            <ArrowLeftRight size={13} aria-hidden /> Authorised return destination required
          </span>
        }
      />
      <RequestForm mode="return" defaults={defaults} />
    </div>
  );
}
