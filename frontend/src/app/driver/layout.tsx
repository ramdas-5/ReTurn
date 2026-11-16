import AppShell from "@/components/AppShell";
import { requireUser } from "@/lib/server";

export const dynamic = "force-dynamic";
export const metadata = {
  title: { default: "Driver", template: "%s · ReTurn" },
  robots: { index: false, follow: false },
};

export default async function DriverLayout({ children }: { children: React.ReactNode }) {
  const me = await requireUser("driver");
  return <AppShell me={me} role="driver">{children}</AppShell>;
}
