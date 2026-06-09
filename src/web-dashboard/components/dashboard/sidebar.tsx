"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Calendar,
  Camera,
  ClipboardList,
  CreditCard,
  FileText,
  LayoutDashboard,
  Mic,
  Settings,
  Users,
  UsersRound,
} from "lucide-react";
import { usePermissions } from "@/lib/hooks/use-permissions";
import { canAccessRoute } from "@/lib/permissions";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/stores/ui-store";
const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/customers", label: "Customers", icon: Users },
  { href: "/jobs", label: "Jobs", icon: ClipboardList },
  { href: "/estimates", label: "Estimates", icon: FileText },
  { href: "/scheduling", label: "Scheduling", icon: Calendar },
  { href: "/photos", label: "Photos", icon: Camera },
  { href: "/voice-notes", label: "Voice Notes", icon: Mic },
  { href: "/team", label: "Team", icon: UsersRound },
  { href: "/billing", label: "Billing", icon: CreditCard },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { role } = usePermissions();
  const collapsed = useUiStore((s) => s.sidebarCollapsed);

  return (
    <aside
      className={cn(
        "flex h-full flex-col border-r border-border bg-card transition-all duration-200",
        collapsed ? "w-16" : "w-60"
      )}
      aria-label="Main navigation"
    >
      <div className={cn("flex h-14 items-center border-b border-border px-4", collapsed && "justify-center px-2")}>
        <Link href="/dashboard" className="text-lg font-bold text-primary">
          {collapsed ? "WT" : "WorkTicket"}
        </Link>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {navItems.map((item) => {
          if (!canAccessRoute(role, item.href)) return null;
          const active = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
                collapsed && "justify-center px-2"
              )}
              title={collapsed ? item.label : undefined}
            >
              <Icon className="h-4 w-4 shrink-0" aria-hidden />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
