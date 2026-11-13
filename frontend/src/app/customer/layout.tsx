import AppShell from "@/components/AppShell";
import { requireUser } from "@/lib/server";

export const dynamic = "force-dynamic";

export const metadata = {
  title: { default: "Customer", template: "%s · ReTurn" },
  robots: { index: false, follow: false },
};

export default async function CustomerLayout({ children }: { children: React.ReactNode }) {
  const me = await requireUser("customer");
  return (
    <AppShell me={me} role="customer">
      {children}
    </AppShell>
  );
}
