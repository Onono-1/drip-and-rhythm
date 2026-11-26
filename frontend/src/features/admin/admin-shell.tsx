"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckSquare,
  FileSpreadsheet,
  LayoutDashboard,
  LogOut,
  Menu,
  QrCode,
  Settings,
  Shield,
  Ticket,
  UserCircle,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { OrganizerWordmark } from "@/components/brand/organizer-wordmark";
import { Button, StatusBadge } from "@/components/ui/primitives";
import { apiFetch } from "@/lib/api-client";
import type { AdminUser } from "@/types/api";

const AdminUserContext = createContext<AdminUser | null>(null);

export function useAdminUser(): AdminUser {
  const ctx = useContext(AdminUserContext);
  if (!ctx) {
    throw new Error("useAdminUser must be used inside AdminGuardShell");
  }
  return ctx;
}

interface NavItem {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  superOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/admin/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/admin/invitations", label: "Invitations", icon: Ticket },
  { href: "/admin/scanner", label: "QR Scanner", icon: QrCode },
  { href: "/admin/check-ins", label: "Check-ins", icon: CheckSquare },
  { href: "/admin/users", label: "Administrators", icon: Users, superOnly: true },
  { href: "/admin/settings", label: "Event Settings", icon: Settings, superOnly: true },
  { href: "/admin/audit-logs", label: "Audit Logs", icon: FileSpreadsheet, superOnly: true },
  { href: "/admin/profile", label: "Profile", icon: UserCircle },
];

export function AdminGuardShell({
  children,
  requireSuperAdmin = false,
}: {
  children: ReactNode;
  requireSuperAdmin?: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const [mobileOpen, setMobileOpen] = useState(false);

  const { data: user, isLoading, isError } = useQuery({
    queryKey: ["admin-me"],
    queryFn: () => apiFetch<AdminUser>("/api/auth/me/"),
    retry: false,
  });

  useEffect(() => {
    if (!isLoading && (isError || !user)) {
      const nextParam = encodeURIComponent(pathname || "/admin/dashboard");
      router.replace(`/admin/login?next=${nextParam}`);
    }
  }, [isError, isLoading, pathname, router, user]);

  const handleLogout = async () => {
    try {
      await apiFetch("/api/auth/logout/", { method: "POST" });
    } finally {
      queryClient.clear();
      router.replace("/admin/login");
    }
  };

  if (isLoading || !user) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-midnight text-champagne">
        <p className="text-sm font-medium">Verifying administrator session...</p>
      </div>
    );
  }

  const isSuper = user.role === "SUPER_ADMIN";
  const visibleItems = NAV_ITEMS.filter((item) => !item.superOnly || isSuper);

  if (requireSuperAdmin && !isSuper) {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center bg-midnight px-6 text-center text-ivory">
        <Shield className="h-10 w-10 text-amber" aria-hidden="true" />
        <h1 className="font-display mt-4 text-3xl tracking-wide uppercase">
          SUPER ADMINISTRATOR ACCESS ONLY
        </h1>
        <p className="mt-2 max-w-md text-sm text-ivory-muted">
          Your account does not have permission to view this section.
        </p>
        <div className="mt-6">
          <Link href="/admin/dashboard">
            <Button>Return to Dashboard</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <AdminUserContext.Provider value={user}>
      <div className="flex min-h-dvh bg-midnight text-ivory">
        {/* Sticky Desktop Sidebar (independent scroll when taller than viewport) */}
        <aside className="hidden w-64 shrink-0 flex-col justify-between gap-6 overflow-y-auto border-r border-champagne/15 bg-espresso p-5 lg:sticky lg:top-0 lg:flex lg:h-dvh">
          <div>
            <Link href="/" className="block">
              <p className="font-display text-2xl tracking-wide text-ivory uppercase">
                DRIP &amp; RHYTHM
              </p>
              <p className="text-[11px] font-semibold text-amber">Host Operations</p>
            </Link>

            <nav aria-label="Administrator" className="mt-7 space-y-1">
              {visibleItems.map((item) => {
                const Icon = item.icon;
                const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex min-h-11 items-center gap-3 rounded-md px-3.5 py-2.5 text-sm font-medium transition-colors ${
                      active
                        ? "bg-burnt text-ivory"
                        : "text-ivory-muted hover:bg-chocolate/60 hover:text-ivory"
                    }`}
                  >
                    <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </nav>
          </div>

          <div className="border-t border-champagne/15 pt-4">
            <div className="mb-3">
              <p className="truncate text-sm font-semibold text-ivory">{user.display_name}</p>
              <p className="truncate text-xs text-ivory-muted">{user.email}</p>
              <div className="mt-1.5">
                <StatusBadge tone={isSuper ? "gold" : "neutral"}>
                  {isSuper ? "Super Admin" : "Admin"}
                </StatusBadge>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="w-full justify-start"
              onClick={() => void handleLogout()}
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              Sign out
            </Button>
          </div>
        </aside>

        {/* Mobile Header + Main Content */}
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex items-center justify-between border-b border-champagne/15 bg-espresso px-4 py-3 lg:hidden">
            <div>
              <p className="font-display text-xl tracking-wide text-ivory uppercase">
                DRIP &amp; RHYTHM
              </p>
              <p className="text-[11px] text-amber">{user.display_name}</p>
            </div>
            <button
              type="button"
              aria-expanded={mobileOpen}
              aria-label={mobileOpen ? "Close navigation menu" : "Open navigation menu"}
              onClick={() => setMobileOpen((prev) => !prev)}
              className="inline-flex h-11 w-11 items-center justify-center rounded-md border border-champagne/25 text-champagne"
            >
              {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </header>

          {mobileOpen && (
            <nav
              aria-label="Mobile administrator"
              className="border-b border-champagne/20 bg-espresso px-4 py-4 lg:hidden"
            >
              <div className="space-y-1">
                {visibleItems.map((item) => {
                  const Icon = item.icon;
                  const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setMobileOpen(false)}
                      className={`flex min-h-11 items-center gap-3 rounded-md px-3.5 py-2.5 text-sm font-medium ${
                        active ? "bg-burnt text-ivory" : "text-ivory-muted hover:bg-chocolate/50"
                      }`}
                    >
                      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </div>
              <div className="mt-4 border-t border-champagne/15 pt-3">
                <Button variant="outline" size="sm" className="w-full" onClick={() => void handleLogout()}>
                  <LogOut className="h-4 w-4" aria-hidden="true" />
                  Sign out
                </Button>
              </div>
            </nav>
          )}

          <main id="main-content" className="mx-auto w-full max-w-7xl flex-1 p-5 sm:p-8">
            {children}
          </main>

          <footer className="border-t border-champagne/10 px-5 py-4 text-xs text-ivory-muted sm:px-8">
            <OrganizerWordmark className="text-[10px]" />
          </footer>
        </div>
      </div>
    </AdminUserContext.Provider>
  );
}
