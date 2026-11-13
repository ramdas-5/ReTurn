import { ShieldCheck } from "lucide-react";

import PartnerProfileForm from "@/components/forms/PartnerProfileForm";
import { VerificationBadge } from "@/components/Status";
import { Callout, Card, PageHeader, StatCard } from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import { requireUser, serverFetch } from "@/lib/server";
import type { PartnerProfile } from "@/lib/types";

export const metadata = { title: "Vehicle & profile" };

type PartnerMe = {
  profile: PartnerProfile;
  stats: {
    assigned_batches: number;
    active_batches: number;
    completed_batches: number;
    completed_parcels: number;
  };
};

export default async function PartnerProfilePage() {
  await requireUser("partner");
  const { profile, stats } = await serverFetch<PartnerMe>("/partners/me");

  return (
    <div>
      <PageHeader
        eyebrow="Eligibility & capacity"
        title="Vehicle & profile"
        description="These settings determine which batches can be offered to you. Administrators verify the account; the matching engine checks the vehicle on every proposal."
        actions={<VerificationBadge status={profile.verification_status} />}
      />

      {profile.verification_status === "verified" ? (
        <div className="mb-5">
          <Callout tone="accent" title="Verified partner">
            Verified {profile.verified_at ? formatDateTime(profile.verified_at) : ""}.{" "}
            {profile.verification_note ?? "No verification note recorded."}
          </Callout>
        </div>
      ) : profile.verification_status === "rejected" ? (
        <div className="mb-5">
          <Callout tone="danger" title="Verification rejected">
            {profile.verification_note ?? "Contact the ReTurn dispatch team for details."} You can still correct your
            profile information.
          </Callout>
        </div>
      ) : (
        <div className="mb-5">
          <Callout tone="warning" title="Pending verification">
            An administrator must verify your account before batch offers become available. Keep your vehicle and service
            area accurate meanwhile.
          </Callout>
        </div>
      )}

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Assigned batches" value={stats.assigned_batches} hint="All time" />
        <StatCard label="Active" value={stats.active_batches} hint="Offered, accepted or on route" tone="accent" />
        <StatCard label="Completed" value={stats.completed_batches} hint="Fully resolved batches" />
        <StatCard label="Parcels delivered" value={stats.completed_parcels} hint="Across completed batches" tone="blue" />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <PartnerProfileForm profile={profile} />
        <div className="space-y-4">
          <Card className="card-pad">
            <h2 className="flex items-center gap-2 text-base font-semibold">
              <ShieldCheck size={18} className="text-accent" aria-hidden /> How eligibility is enforced
            </h2>
            <ul className="mt-2 space-y-2 text-[13px] leading-6 text-muted">
              <li>• The account must be verified by an administrator.</li>
              <li>• Availability must be “available” for new offers.</li>
              <li>• Weight and volume capacity must cover the batch&apos;s peak load after every stop.</li>
              <li>• Fragile or restricted items require explicit vehicle capability.</li>
              <li>• Every pickup and drop-off area must be inside your declared service areas.</li>
            </ul>
          </Card>
          <Callout tone="info" title="Changes are audited">
            Vehicle, capacity and availability updates are recorded in the audit trail. Changing them does not retroactively
            invalidate an accepted batch, but administrators can reassign with a reason.
          </Callout>
          <Card className="card-pad">
            <h2 className="text-base font-semibold">Account reference</h2>
            <dl className="mt-2 space-y-2 text-[12px]">
              <div className="flex justify-between gap-2">
                <dt className="text-muted">Partner profile</dt>
                <dd className="mono">#{profile.id}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted">Account email</dt>
                <dd>{profile.email}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted">Vehicle</dt>
                <dd className="capitalize">{profile.vehicle_type}</dd>
              </div>
            </dl>
          </Card>
        </div>
      </div>
    </div>
  );
}
