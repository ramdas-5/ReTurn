import { Bike, ShieldCheck, Truck } from "lucide-react";
import Link from "next/link";

import { PartnerVerificationActions } from "@/components/admin/AdminActions";
import { CompletionBar } from "@/components/admin/PartnerMeter";
import { VerificationBadge } from "@/components/Status";
import { Callout, Card, EmptyState, PageHeader, StatCard } from "@/components/ui";
import { formatDateTime, formatWeight } from "@/lib/format";
import { requireUser, serverFetchList } from "@/lib/server";
import type { PartnerProfile } from "@/lib/types";

export const metadata = { title: "Partners" };

export default async function AdminPartnersPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string }>;
}) {
  await requireUser("admin");
  const params = await searchParams;
  const { data: all } = await serverFetchList<PartnerProfile>("/partners");
  const filter = params.status && ["pending", "verified", "rejected"].includes(params.status)
    ? params.status
    : null;
  const partners = filter ? all.filter((partner) => partner.verification_status === filter) : all;

  return (
    <div>
      <PageHeader
        eyebrow="Fleet eligibility"
        title="Delivery partners"
        description="Verify accounts and inspect the vehicle envelope the matching engine will use. Verification alone does not guarantee an offer: availability, capacity, handling and service area still apply."
      />

      <div className="mb-5 grid gap-4 sm:grid-cols-3">
        <StatCard label="Verified" value={all.filter((partner) => partner.verification_status === "verified").length} hint="Eligible for offers" icon={<ShieldCheck size={17} aria-hidden />} tone="accent" />
        <StatCard label="Pending" value={all.filter((partner) => partner.verification_status === "pending").length} hint="Needs review" icon={<Truck size={17} aria-hidden />} tone="amber" />
        <StatCard label="Rejected" value={all.filter((partner) => partner.verification_status === "rejected").length} hint="Not offerable" tone="red" />
      </div>

      <div className="mb-5 flex flex-wrap gap-2">
        {[
          { value: "", label: "All partners" },
          { value: "pending", label: "Pending" },
          { value: "verified", label: "Verified" },
          { value: "rejected", label: "Rejected" },
        ].map((option) => (
          <Link
            key={option.value}
            href={option.value ? `/admin/partners?status=${option.value}` : "/admin/partners"}
            className={`btn btn-sm ${filter === (option.value || null) ? "btn-primary" : "btn-secondary"}`}
          >
            {option.label}
          </Link>
        ))}
      </div>

      {partners.length === 0 ? (
        <EmptyState icon={<Truck size={20} aria-hidden />} title="No partners here" description="No partner profile matches this filter." />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {partners.map((partner) => (
            <Card key={partner.id} className="card-pad" as="article">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                  <span className="flex h-10 w-10 items-center justify-center rounded-control bg-surface-muted text-ink-2">
                    {partner.vehicle_type === "bike" ? <Bike size={18} aria-hidden /> : <Truck size={18} aria-hidden />}
                  </span>
                  <div>
                    <h2 className="text-base font-bold">{partner.name}</h2>
                    <p className="text-[12px] text-muted">{partner.company_name}</p>
                    <p className="text-[11px] text-muted">{partner.email} · {partner.phone ?? "no phone"}</p>
                  </div>
                </div>
                <VerificationBadge status={partner.verification_status} />
              </div>

              <dl className="mt-4 grid grid-cols-2 gap-3 text-[12px]">
                <div>
                  <dt className="text-[10px] uppercase tracking-wide text-muted">Vehicle</dt>
                  <dd className="mt-0.5 capitalize">{partner.vehicle_type}</dd>
                </div>
                <div>
                  <dt className="text-[10px] uppercase tracking-wide text-muted">Availability</dt>
                  <dd className="mt-0.5 capitalize">{partner.availability.replaceAll("_", " ")}</dd>
                </div>
                <div>
                  <dt className="text-[10px] uppercase tracking-wide text-muted">Weight capacity</dt>
                  <dd className="mono mt-0.5">{formatWeight(partner.max_weight_kg)}</dd>
                </div>
                <div>
                  <dt className="text-[10px] uppercase tracking-wide text-muted">Volume capacity</dt>
                  <dd className="mono mt-0.5">{partner.max_volume_m3.toFixed(3)} m³</dd>
                </div>
                <div>
                  <dt className="text-[10px] uppercase tracking-wide text-muted">Handling</dt>
                  <dd className="mt-0.5">
                    {[partner.accepts_fragile ? "Fragile" : null, partner.accepts_restricted ? "Restricted" : null]
                      .filter(Boolean)
                      .join(", ") || "Standard only"}
                  </dd>
                </div>
                <div>
                  <dt className="text-[10px] uppercase tracking-wide text-muted">Operating hours</dt>
                  <dd className="mt-0.5">{partner.operating_hours.start_hour}:00 – {partner.operating_hours.end_hour}:00</dd>
                </div>
              </dl>

              <div className="mt-3">
                <CompletionBar
                  maxWeight={partner.max_weight_kg}
                  maxVolume={partner.max_volume_m3}
                  referenceWeight={40}
                  referenceVolume={0.25}
                />
              </div>

              <p className="mt-3 text-[12px] leading-5 text-muted">
                Service areas: {partner.service_areas.length ? partner.service_areas.join(", ") : "No restriction declared"}
              </p>
              {partner.verification_note ? (
                <p className="mt-1 text-[11px] leading-5 text-muted">Note: {partner.verification_note}</p>
              ) : null}
              <p className="mt-1 text-[10px] text-muted">
                Profile created {formatDateTime(partner.created_at)}
                {partner.verified_at ? ` · verified ${formatDateTime(partner.verified_at)}` : ""}
              </p>

              <div className="mt-4 border-t pt-3">
                <PartnerVerificationActions profile={partner} />
              </div>
            </Card>
          ))}
        </div>
      )}

      <div className="mt-5">
        <Callout tone="warning" title="Verification is audited">
          Verify only after checking vehicle documents and service area. Rejections require a note that the partner can see.
          Changing verification status does not rewrite existing batch history.
        </Callout>
      </div>
    </div>
  );
}
