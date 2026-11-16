import OrderForm from "@/components/forms/OrderForm";
import { PageHeader, Callout } from "@/components/ui";

export const metadata = { title: "Return a product" };

export default function NewReturnPage() {
  return (
    <div>
      <PageHeader
        eyebrow="New return"
        title="Return a product to its authorised destination"
        description="Returns can go to the original business, a warehouse, an authorised hub or a return processing centre. ReTurn never assumes one central warehouse."
      />
      <Callout tone="info" title="Merchant approval">
        If the merchant requires approval, mark it here. The parcel will still be reviewed by a manager and will not be collected until the workflow allows it.
      </Callout>
      <div className="mt-5"><OrderForm serviceType="return" /></div>
    </div>
  );
}
