import AppShell from "@/components/AppShell";
import { requireUser } from "@/lib/server";

export const dynamic = "force-dynamic";
export const metadata = {
  title: { default: "Consumer", template: "%s · ReTurn" },
  robots: { index: false, follow: false },
};

export default async function ConsumerLayout({ children }: { children: React.ReactNode }) {
  const me = await requireUser("consumer");
  return <AppShell me={me} role="consumer">{children}</AppShell>;
}
