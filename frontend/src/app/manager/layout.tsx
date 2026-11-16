import AppShell from "@/components/AppShell";
import { requireUser } from "@/lib/server";

export const dynamic = "force-dynamic";
export const metadata = {
  title: { default: "Manager", template: "%s · ReTurn" },
  robots: { index: false, follow: false },
};

export default async function ManagerLayout({ children }: { children: React.ReactNode }) {
  const me = await requireUser("manager");
  return <AppShell me={me} role="manager">{children}</AppShell>;
}
