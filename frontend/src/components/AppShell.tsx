import Link from "next/link";
import type { ReactNode } from "react";

import { Brand } from "@/components/Brand";
import { SidebarNav, MobileNav, type NavItem } from "@/components/AppNav";
import { NotificationMenu, TopBarUser } from "@/components/TopBarActions";
import type { AuthMe, Role } from "@/lib/types";

const CUSTOMER_NAV: NavItem[] = [
  { href: "/customer", label: "Overview", icon: "dashboard", exact: true },
  { href: "/customer/requests", label: "My Requests", icon: "requests" },
  { href: "/customer/history", label: "History", icon: "history" },
  { href: "/customer/settings", label: "Profile & Settings", icon: "settings" },
];

const PARTNER_NAV: NavItem[] = [
  { href: "/partner", label: "Overview", icon: "dashboard", exact: true },
  { href: "/partner/batches", label: "Available Batches", icon: "batches" },
  { href: "/partner#active-route", label: "Active Route", icon: "route" },
  { href: "/partner/history", label: "Completed Work", icon: "history" },
  { href: "/partner/profile", label: "Vehicle & Profile", icon: "profile" },
];

const ADMIN_NAV: NavItem[] = [
  { href: "/admin", label: "Overview", icon: "dashboard", exact: true },
  { href: "/admin/requests", label: "Requests", icon: "requests" },
  { href: "/admin/batches", label: "Batches", icon: "batches" },
  { href: "/admin/routes", label: "Route Monitor", icon: "monitor" },
  { href: "/admin/customers", label: "Customers", icon: "customers" },
  { href: "/admin/partners", label: "Partners", icon: "partners" },
  { href: "/admin/issues", label: "Issues", icon: "issues" },
  { href: "/admin/analytics", label: "Analytics", icon: "analytics" },
];

export const NAV_BY_ROLE: Record<Role, NavItem[]> = {
  customer: CUSTOMER_NAV,
  partner: PARTNER_NAV,
  admin: ADMIN_NAV,
};

const ROLE_LABEL: Record<Role, string> = {
  customer: "Customer workspace",
  partner: "Partner route desk",
  admin: "Dispatch control room",
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
  const items = NAV_BY_ROLE[role];
  const home = role === "admin" ? "/admin" : role === "partner" ? "/partner" : "/customer";

  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[252px] flex-col bg-ink px-1 pb-5 pt-6 text-white lg:flex">
        <div className="px-4">
          <Brand href={home} invert />
          <p className="mt-2 text-[11px] uppercase tracking-[0.16em] text-white/45">{ROLE_LABEL[role]}</p>
        </div>
        {role === "customer" ? (
          <div className="mt-5 space-y-2 px-3">
            <Link
              href="/customer/returns/new"
              className="flex min-h-[42px] items-center justify-center rounded-control bg-lime px-3 text-[13px] font-semibold text-ink transition hover:brightness-95"
            >
              Return a product
            </Link>
            <Link
              href="/customer/parcels/new"
              className="flex min-h-[42px] items-center justify-center rounded-control border border-white/20 px-3 text-[13px] font-semibold text-white transition hover:bg-white/10"
            >
              Send a parcel
            </Link>
          </div>
        ) : null}
        <SidebarNav items={items} />
        <div className="mt-auto px-4">
          <div className="rounded-card border border-white/10 bg-white/[0.04] p-3">
            <p className="truncate text-[13px] font-semibold">{me.user.name}</p>
            <p className="truncate text-[11px] text-white/55">{me.user.email}</p>
            {me.partner_profile ? (
              <p className="mt-2 text-[11px] text-white/55">
                {me.partner_profile.company_name} ·{" "}
                <span className="capitalize">{me.partner_profile.verification_status}</span>
              </p>
            ) : null}
          </div>
          <p className="mt-3 px-1 text-[10px] leading-4 text-white/35">
            ReTurn coordinates requests; it does not operate courier vehicles.
          </p>
        </div>
      </aside>

      <div className="flex min-h-screen flex-col lg:pl-[252px]">
        <header className="sticky top-0 z-30 flex h-[64px] items-center gap-3 border-b bg-surface/95 px-4 backdrop-blur sm:h-[72px] sm:px-6">
          <div className="lg:hidden">
            <Brand href={home} compact />
          </div>
          <div className="ml-auto flex items-center gap-1 sm:gap-2">
            {role === "customer" ? (
              <div className="mr-1 hidden items-center gap-2 sm:flex">
                <Link href="/customer/returns/new" className="btn btn-primary btn-sm">
                  New return
                </Link>
                <Link href="/customer/parcels/new" className="btn btn-secondary btn-sm">
                  Send parcel
                </Link>
              </div>
            ) : null}
            <NotificationMenu />
            <TopBarUser user={me.user} />
          </div>
        </header>

        <main className="flex-1 px-4 pb-24 pt-6 sm:px-6 lg:px-8 lg:pb-10">
          <div className="mx-auto w-full max-w-[1180px]">{children}</div>
        </main>
        <MobileNav items={items} />
      </div>
    </div>
  );
}
