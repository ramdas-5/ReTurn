import AppShell from "@/components/AppShell";
import { requireUser } from "@/lib/server";

export const dynamic = "force-dynamic";

export const metadata = {
  title: { default: "Partner", template: "%s · ReTurn" },
  robots: { index: false, follow: false },
};

export default async function PartnerLayout({ children }: { children: React.ReactNode }) {
  const me = await requireUser("partner");
  return (
    <AppShell me={me} role="partner">
      {children}
    </AppShell>
  );
}
