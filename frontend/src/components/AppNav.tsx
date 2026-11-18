"use client";

import {
  AlertTriangle,
  BarChart3,
  Building2,
  ClipboardList,
  Gauge,
  History,
  LayoutDashboard,
  Map,
  MapPin,
  Package,
  Route,
  Settings,
  ShieldCheck,
  Truck,
  UserRound,
  Users,
  Warehouse,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/cn";

export type NavItem = { href: string; label: string; icon: string; exact?: boolean };

const ICONS: Record<string, React.ComponentType<{ size?: number; strokeWidth?: number; "aria-hidden"?: boolean }>> = {
  dashboard: LayoutDashboard,
  orders: ClipboardList,
  history: History,
  settings: Settings,
  batches: Package,
  route: Route,
  profile: UserRound,
  customers: Users,
  users: Users,
  issues: AlertTriangle,
  analytics: BarChart3,
  monitor: Map,
  truck: Truck,
  duty: Gauge,
  areas: MapPin,
  business: Building2,
  fleet: Warehouse,
  audit: ShieldCheck,
};

function useIsActive() {
  const pathname = usePathname() ?? "";
  return (item: NavItem) =>
    item.exact ? pathname === item.href : pathname === item.href || pathname.startsWith(`${item.href}/`);
}

export function SidebarNav({ items }: { items: NavItem[] }) {
  const isActive = useIsActive();
  return (
    <nav aria-label="Primary" className="mt-5 space-y-1 overflow-y-auto px-3 pb-4">
      {items.map((item) => {
        const Icon = ICONS[item.icon] ?? LayoutDashboard;
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={isActive(item) ? "page" : undefined}
            className={cn("nav-item", isActive(item) && "nav-item-active")}
          >
            <Icon size={17} strokeWidth={2} aria-hidden />
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

export function MobileNav({ items }: { items: NavItem[] }) {
  const isActive = useIsActive();
  return (
    <nav
      aria-label="Primary mobile"
      className="on-dark fixed inset-x-0 bottom-0 z-40 border-t bg-inverse px-1 pb-[env(safe-area-inset-bottom)] lg:hidden"
    >
      <div className="flex items-stretch justify-around">
        {items.slice(0, 5).map((item) => {
          const Icon = ICONS[item.icon] ?? LayoutDashboard;
          const active = isActive(item);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex min-h-[56px] flex-1 flex-col items-center justify-center gap-1 border-t-2 px-1 py-2 text-2xs font-medium",
                active ? "border-primary text-white" : "border-transparent text-muted",
              )}
            >
              <Icon size={19} strokeWidth={2} aria-hidden />
              <span className="line-clamp-1 text-center">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
