import OrderForm from "@/components/forms/OrderForm";
import { PageHeader } from "@/components/ui";

export const metadata = { title: "Send a parcel" };

export default function NewParcelPage() {
  return (
    <div>
      <PageHeader
        eyebrow="New parcel"
        title="Send a parcel to a recipient"
        description="Add the exterior photograph, choose a real pickup window, and let a manager match compatible work. No driver is promised until assignment."
      />
      <OrderForm serviceType="parcel" />
    </div>
  );
}
