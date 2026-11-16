"use client";

import { PageHeader } from "@/components/ui";
import DriverDutyControls from "@/components/DriverDutyControls";

export default function DriverDutyPage() {
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader eyebrow="Duty & availability" title="Control when you are available" description="Duty status and heartbeat determine whether dispatch can assign work. Location is only shared with explicit consent while on duty." />
      <DriverDutyControls />
      <div className="card card-pad mt-5 text-sm leading-6 text-muted">
        <p className="font-semibold text-ink">Privacy</p>
        <p className="mt-2">ReTurn never fabricates a location. If you do not share one, managers see “tracking unavailable”. Going off duty stops location collection and removes you from live dispatch.</p>
      </div>
    </div>
  );
}
