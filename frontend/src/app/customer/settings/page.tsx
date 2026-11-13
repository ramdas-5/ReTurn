import { ShieldCheck } from "lucide-react";

import SettingsForm from "@/components/forms/SettingsForm";
import { Callout, PageHeader } from "@/components/ui";
import { requireUser } from "@/lib/server";

export const metadata = { title: "Profile & settings" };

export default async function CustomerSettingsPage() {
  const me = await requireUser("customer");
  return (
    <div>
      <PageHeader
        eyebrow="Account"
        title="Profile & settings"
        description="Keep your contact details current so a verified partner can reach you about a collection."
      />
      <div className="mb-6">
        <Callout tone="info" title="Privacy boundaries">
          Your email, phone and address details are only exposed to you, an assigned verified partner for an accepted
          batch, and authorized administrators. They are never embedded in public pages or shared with other customers.
        </Callout>
      </div>
      <SettingsForm user={me.user} />
      <div className="mt-6 card card-pad">
        <h2 className="flex items-center gap-2 text-base font-semibold">
          <ShieldCheck size={18} className="text-accent" aria-hidden /> Security notes
        </h2>
        <ul className="mt-2 space-y-1.5 text-[13px] leading-6 text-muted">
          <li>• Sessions are server-side, stored hashed, and delivered through an HttpOnly cookie.</li>
          <li>• Every mutating request requires a matching CSRF token.</li>
          <li>• Passwords are hashed with Argon2id and never written to logs.</li>
          <li>• Sign-in attempts are rate-limited. Repeated failures are not silently ignored.</li>
        </ul>
      </div>
    </div>
  );
}
