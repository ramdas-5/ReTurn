import { Truck } from "lucide-react";

import RequestForm from "@/components/forms/RequestForm";
import { PageHeader } from "@/components/ui";
import { requireUser } from "@/lib/server";

export const metadata = { title: "Send a parcel" };

export default async function NewParcelPage() {
  await requireUser("customer");
  const now = Date.now();
  const defaults = {
    start: new Date(now + 90 * 60 * 1000).toISOString(),
    end: new Date(now + 180 * 60 * 1000).toISOString(),
    deadline: new Date(now + 330 * 60 * 1000).toISOString(),
  };

  return (
    <div>
      <PageHeader
        back={{ href: "/customer", label: "Customer overview" }}
        eyebrow="Parcel lane"
        title="Send a parcel"
        description="The recipient's own address is preserved exactly. ReTurn may propose sharing the route with a compatible return or parcel nearby — only if every operational check passes."
        actions={
          <span className="chip chip-blue">
            <Truck size={13} aria-hidden /> Recipient delivery address
          </span>
        }
      />
      <RequestForm mode="parcel" defaults={defaults} />
    </div>
  );
}
