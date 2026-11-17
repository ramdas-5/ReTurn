import Link from "next/link";
import type { ReactNode } from "react";

import { Brand } from "@/components/Brand";
import { MobileNav, SidebarNav, type NavItem } from "@/components/AppNav";
import { NotificationMenu, TopBarUser } from "@/components/TopBarActions";
import type { AuthMe, Role } from "@/lib/types";

const NAV: Record<Role, NavItem[]> = {
  consumer: [
    { href: "/consumer", label: "Overview", icon: "dashboard", exact: true },
    { href: "/consumer/orders", label: "My orders", icon: "orders" },
    { href: "/consumer/history", label: "History", icon: "history" },
    { href: "/consumer/addresses", label: "Saved addresses", icon: "areas" },
    { href: "/consumer/business", label: "Business profile", icon: "business" },
    { href: "/consumer/support", label: "Support & issues", icon: "issues" },
    { href: "/consumer/notifications", label: "Notifications", icon: "monitor" },
    { href: "/consumer/settings", label: "Profile & settings", icon: "settings" },
  ],
  driver: [
    { href: "/driver", label: "Overview", icon: "dashboard", exact: true },
    { href: "/driver/assignments", label: "Assigned orders", icon: "orders" },
    { href: "/driver/batches", label: "Assigned batches", icon: "batches" },
    { href: "/driver/duty", label: "Duty & availability", icon: "duty" },
    { href: "/driver/history", label: "Delivery history", icon: "history" },
    { href: "/driver/vehicle", label: "Vehicle profile", icon: "profile" },
    { href: "/driver/issues", label: "Report an issue", icon: "issues" },
    { href: "/driver/notifications", label: "Notifications", icon: "monitor" },
  ],
  manager: [
    { href: "/manager", label: "Overview", icon: "dashboard", exact: true },
    { href: "/manager/orders", label: "Order management", icon: "orders" },
    { href: "/manager/assignments", label: "Pending assignments", icon: "truck" },
    { href: "/manager/matching", label: "Smart matching", icon: "route" },
    { href: "/manager/batches", label: "Batches", icon: "batches" },
    { href: "/manager/drivers", label: "Drivers", icon: "customers" },
    { href: "/manager/routes", label: "Route management", icon: "route" },
    { href: "/manager/progress", label: "Delivery progress", icon: "monitor" },
    { href: "/manager/live", label: "Live tracking", icon: "monitor" },
    { href: "/manager/proofs", label: "Proof verification", icon: "audit" },
    { href: "/manager/issues", label: "Delivery issues", icon: "issues" },
    { href: "/manager/analytics", label: "Reports", icon: "analytics" },
  ],
  admin: [
    { href: "/admin", label: "Overview", icon: "dashboard", exact: true },
    { href: "/admin/analytics", label: "Analytics", icon: "analytics" },
    { href: "/admin/operations", label: "Live operations", icon: "monitor" },
    { href: "/admin/orders", label: "All orders", icon: "orders" },
    { href: "/admin/batches", label: "All batches", icon: "batches" },
    { href: "/admin/consumers", label: "Consumers", icon: "customers" },
    { href: "/admin/businesses", label: "Businesses", icon: "business" },
    { href: "/admin/managers", label: "Managers", icon: "users" },
    { href: "/admin/drivers", label: "Drivers", icon: "truck" },
    { href: "/admin/vehicles", label: "Vehicles", icon: "fleet" },
    { href: "/admin/service-areas", label: "Service areas", icon: "areas" },
    { href: "/admin/matching", label: "Matching config", icon: "route" },
    { href: "/admin/proofs", label: "Proof audit", icon: "audit" },
    { href: "/admin/audit", label: "Audit logs", icon: "audit" },
    { href: "/admin/settings", label: "Platform settings", icon: "settings" },
    { href: "/admin/accounts/new", label: "Create account", icon: "users" },
  ],
};

const ROLE_LABEL: Record<Role, string> = {
  consumer: "Consumer workspace",
  driver: "Driver field app",
  manager: "Operations desk",
  admin: "Platform control",
};

export default function AppShell({
  me,
  role,
  children,
}: {
  me: AuthMe;
  role: Role;
  children: ReactNode;
}) {
  const items = NAV[role];
  const home = `/${role}`;

  return (
    <div className="min-h-screen">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <aside className="on-dark fixed inset-y-0 left-0 z-40 hidden w-[252px] flex-col bg-canvas pb-5 pt-6 text-white lg:flex">
        <div className="px-4">
          <Brand href={home} invert />
          <p className="mt-2 text-2xs uppercase tracking-[0.16em] text-white/70">
            {ROLE_LABEL[role]}
          </p>
        </div>
        {role === "consumer" ? (
          <div className="mt-4 space-y-2 px-3">
            <Link
              href="/consumer/parcels/new"
              className="flex min-h-[42px] items-center justify-center rounded-control bg-lime px-3 text-sm font-semibold text-canvas transition hover:brightness-95"
            >
              Send a parcel
            </Link>
            <Link
              href="/consumer/returns/new"
              className="flex min-h-[42px] items-center justify-center rounded-control border border-white/30 px-3 text-sm font-semibold text-white transition hover:bg-white/10"
            >
              Return a product
            </Link>
          </div>
        ) : null}
        <SidebarNav items={items} />
        <div className="mt-auto px-4 pt-3">
          <div className="rounded-card border border-white/15 bg-white/[0.06] p-3">
            <p className="truncate text-sm font-semibold">{me.user.full_name}</p>
            <p className="truncate text-2xs text-white/70">{me.user.email}</p>
            <p className="mt-1 text-2xs uppercase tracking-wide text-white/70">{role}</p>
          </div>
          <p className="mt-3 px-1 text-2xs leading-4 text-white/60">
            ReTurn coordinates feasible shared routes. It does not operate the vehicles.
          </p>
        </div>
      </aside>

      <div className="flex min-h-screen flex-col lg:pl-[252px]">
        <header className="on-dark sticky top-0 z-30 flex h-[64px] items-center gap-3 border-b bg-canvas/90 px-4 backdrop-blur sm:h-[72px] sm:px-6">
          <div className="lg:hidden">
            <Brand href={home} compact />
          </div>
          <div className="ml-auto flex items-center gap-1 sm:gap-2">
            {role === "consumer" ? (
              <div className="mr-1 hidden items-center gap-2 sm:flex">
                <Link href="/consumer/parcels/new" className="btn btn-primary btn-sm">
                  New parcel
                </Link>
                <Link href="/consumer/returns/new" className="btn btn-secondary btn-sm">
                  New return
                </Link>
              </div>
            ) : null}
            <NotificationMenu />
            <TopBarUser user={me.user} />
          </div>
        </header>

        <main id="main" tabIndex={-1} className="flex-1 px-4 pb-24 pt-6 sm:px-6 lg:px-8 lg:pb-10">
          <div className="mx-auto w-full max-w-[1180px]">{children}</div>
        </main>
        <MobileNav items={items} />
      </div>
    </div>
  );
}
