import AppShell from "@/components/AppShell";
import { requireUser } from "@/lib/server";

export const dynamic = "force-dynamic";
export const metadata = {
  title: { default: "Administrator", template: "%s · ReTurn" },
  robots: { index: false, follow: false },
};

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const me = await requireUser("admin");
  return <AppShell me={me} role="admin">{children}</AppShell>;
}
