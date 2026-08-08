"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ClipboardCheck,
  ClipboardPlus,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  ScanSearch,
  Settings,
  Users,
  X,
} from "lucide-react";

import { getAccountSession, logoutAccount, type AccountSession } from "@/lib/api";
import { cn } from "./ui";

const PUBLIC_PATHS = new Set([
  "/",
  "/signup",
  "/login",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
  "/accept-invite",
  "/terms",
  "/privacy",
  "/company-proof",
]);

const NAV_ITEMS = [
  { href: "/review/new", label: "Intake", icon: ClipboardPlus },
  { href: "/app", label: "Decision Packets", icon: LayoutDashboard },
  { href: "/review", label: "Review Queue", icon: ClipboardCheck },
  { href: "/history", label: "Outcomes & Memory", icon: History },
  { href: "/market-scanner", label: "Market Scanner", icon: ScanSearch },
  { href: "/team", label: "Team", icon: Users },
  { href: "/admin", label: "Admin", icon: Settings },
] as const;

const LAB_PATH_PREFIXES = [
  "/advanced",
  "/alpha",
  "/calibration",
  "/cli-design",
  "/discovery",
  "/enterprise",
  "/execution-intelligence",
  "/governance",
  "/market-scanner",
  "/markets",
  "/platform",
  "/relay-benchmarks",
  "/reports",
  "/signals",
] as const;

const labsEnabled =
  process.env.NEXT_PUBLIC_ENABLE_LABS === "true" ||
  (process.env.NEXT_PUBLIC_ENABLE_LABS === undefined && process.env.NODE_ENV !== "production");

const marketScannerEnabled =
  process.env.NEXT_PUBLIC_ENABLE_MARKET_SCANNER === "true" ||
  (process.env.NEXT_PUBLIC_ENABLE_MARKET_SCANNER === undefined && process.env.NODE_ENV !== "production");

const MARKET_SCANNER_PATH_PREFIXES = ["/market-scanner", "/markets"] as const;
const MARKET_SCANNER_ROLES = new Set(["analyst", "reviewer", "owner", "admin"]);

function activePath(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || "/";
  const isPublic = PUBLIC_PATHS.has(pathname);
  const isMarketScannerPath = MARKET_SCANNER_PATH_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
  const isHiddenLab = LAB_PATH_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  ) && !(isMarketScannerPath && marketScannerEnabled);
  const [profile, setProfile] = useState<AccountSession | null>(null);
  const [checking, setChecking] = useState(!isPublic);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    if (isPublic) {
      setChecking(false);
      return;
    }
    if (isHiddenLab && !labsEnabled) {
      window.location.replace("/app");
      return;
    }
    let active = true;
    setChecking(true);
    getAccountSession()
      .then((session) => {
        if (!active) return;
        if (isMarketScannerPath && !MARKET_SCANNER_ROLES.has(session.organization.role)) {
          window.location.replace("/app");
          return;
        }
        setProfile(session);
      })
      .catch(() => {
        const returnTo = encodeURIComponent(pathname);
        window.location.assign(`/login?returnTo=${returnTo}`);
      })
      .finally(() => {
        if (active) setChecking(false);
      });
    return () => {
      active = false;
    };
  }, [isHiddenLab, isMarketScannerPath, isPublic, pathname]);

  if (isPublic) return <>{children}</>;

  if (checking || !profile) {
    return (
      <main className="grid min-h-screen place-items-center bg-fog px-6 text-ink">
        <div className="text-center">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-teal/25 border-t-teal" />
          <p className="mt-4 text-sm text-ink/65">Opening your decision workspace…</p>
        </div>
      </main>
    );
  }

  const navItems = NAV_ITEMS.filter(
    (item) => item.href !== "/market-scanner" ||
      (marketScannerEnabled && MARKET_SCANNER_ROLES.has(profile.organization.role)),
  );

  async function signOut() {
    await logoutAccount();
    window.location.assign("/");
  }

  return (
    <div className="min-h-screen bg-fog text-ink">
      <div className="mx-auto flex w-full max-w-[1600px]">
        <aside className="hidden min-h-screen w-64 shrink-0 border-r border-line/80 bg-paper/90 p-4 lg:flex lg:flex-col">
          <Link href="/app" className="focus-ring rounded-md px-2 py-2">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-teal">Ambrosia</p>
            <p className="mt-1 text-xs text-ink/55">Governed investment decisions</p>
          </Link>

          <nav className="mt-7 flex-1">
            <ul className="space-y-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                const active = activePath(pathname, item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={cn(
                        "focus-ring flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition",
                        active ? "bg-teal/10 text-teal" : "text-ink/75 hover:bg-white/5 hover:text-ink",
                      )}
                    >
                      <Icon className="h-4 w-4" />
                      <span>{item.label}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          <section className="rounded-lg border border-line bg-fog/70 p-3">
            <p className="truncate text-sm font-medium text-ink">{profile.organization.name}</p>
            <p className="mt-0.5 truncate text-xs text-ink/55">{profile.user.email}</p>
            <div className="mt-3 flex items-center justify-between">
              <span className="rounded-full bg-teal/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-teal">
                {profile.organization.role}
              </span>
              <button
                type="button"
                onClick={signOut}
                className="focus-ring rounded-md p-2 text-ink/55 hover:bg-white/5 hover:text-ink"
                aria-label="Sign out"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          </section>
        </aside>

        <main className="min-h-screen min-w-0 flex-1 p-4 pb-24 lg:p-8 lg:pb-8">{children}</main>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-paper/95 p-2 backdrop-blur lg:hidden">
        <ul className="grid grid-cols-5 gap-1">
          {navItems.slice(0, 4).map((item) => {
            const Icon = item.icon;
            const active = activePath(pathname, item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "focus-ring flex flex-col items-center gap-1 rounded-md px-1 py-2 text-[10px] font-medium",
                    active ? "bg-teal/10 text-teal" : "text-ink/70",
                  )}
                >
                  <Icon className="h-4 w-4" />
                  <span className="max-w-full truncate">{item.label.split(" ")[0]}</span>
                </Link>
              </li>
            );
          })}
          <li>
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              className="focus-ring flex w-full flex-col items-center gap-1 rounded-md px-1 py-2 text-[10px] font-medium text-ink/70"
            >
              <Menu className="h-4 w-4" />
              <span>More</span>
            </button>
          </li>
        </ul>
      </nav>

      {mobileMenuOpen ? (
        <div className="fixed inset-0 z-50 bg-black/60 p-3 lg:hidden" onClick={() => setMobileMenuOpen(false)}>
          <section
            className="ml-auto w-full max-w-sm rounded-xl border border-line bg-paper p-4 shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold text-ink">{profile.organization.name}</p>
                <p className="text-xs text-ink/55">{profile.user.email}</p>
              </div>
              <button className="focus-ring rounded-md p-2" onClick={() => setMobileMenuOpen(false)} aria-label="Close menu">
                <X className="h-4 w-4" />
              </button>
            </div>
            <ul className="space-y-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                return (
                  <li key={item.href}>
                    <Link href={item.href} onClick={() => setMobileMenuOpen(false)} className="focus-ring flex items-center gap-3 rounded-md px-3 py-3 text-sm text-ink/80 hover:bg-white/5">
                      <Icon className="h-4 w-4" /> {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
            <button type="button" onClick={signOut} className="focus-ring mt-4 flex w-full items-center justify-center gap-2 rounded-md border border-line px-3 py-2.5 text-sm text-ink/75">
              <LogOut className="h-4 w-4" /> Sign out
            </button>
          </section>
        </div>
      ) : null}
    </div>
  );
}
