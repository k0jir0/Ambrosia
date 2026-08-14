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
  Search,
  ScanSearch,
  Settings,
  TerminalSquare,
  TestTubeDiagonal,
  Activity,
  BarChart3,
  RadioTower,
  RefreshCw,
  Users,
  X,
} from "lucide-react";

import {
  getAccountSession,
  isAuthenticationRequired,
  logoutAccount,
  type AccountSession,
} from "@/lib/api";
import { getRouteAvailability, isRouteAvailable, PUBLIC_PATHS } from "@/lib/route-availability";
import { CommandPalette } from "./command-palette";
import { cn } from "./ui";

const NAV_ITEMS = [
  { href: "/review/new", label: "Intake", icon: ClipboardPlus },
  { href: "/app", label: "Decision Packets", icon: LayoutDashboard },
  { href: "/review", label: "Review Queue", icon: ClipboardCheck },
  { href: "/history", label: "Outcomes & Memory", icon: History },
  { href: "/market-scanner", label: "Market Scanner", icon: ScanSearch },
  { href: "/markets/AAPL", label: "Market Intelligence", icon: BarChart3 },
  { href: "/alpha", label: "Alpha Lab", icon: TestTubeDiagonal },
  { href: "/signals", label: "Signals Lab", icon: RadioTower },
  { href: "/cli-design", label: "CLI Guide", icon: TerminalSquare },
  { href: "/operations", label: "Operations", icon: Activity },
  { href: "/team", label: "Team", icon: Users },
  { href: "/admin", label: "Admin", icon: Settings },
] as const;

const SESSION_RETRY_DELAYS_MS = [250, 750] as const;
const SESSION_REVALIDATION_MS = 90_000;

function activePath(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || "/";
  const isPublic = PUBLIC_PATHS.has(pathname);
  const routeAvailability = getRouteAvailability(pathname);
  const routeEnabled = routeAvailability?.enabled ?? true;
  const [profile, setProfile] = useState<AccountSession | null>(null);
  const [checking, setChecking] = useState(!isPublic);
  const [sessionIssue, setSessionIssue] = useState<string | null>(null);
  const [sessionRetryKey, setSessionRetryKey] = useState(0);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const sessionId = profile?.session.id;

  useEffect(() => {
    if (isPublic) {
      setChecking(false);
      return;
    }
    if (profile) {
      setChecking(false);
      return;
    }

    let active = true;
    let retryTimer: number | undefined;

    async function loadSession(attempt: number) {
      setChecking(true);
      try {
        const session = await getAccountSession();
        if (!active) return;
        if (!isRouteAvailable(pathname, session.organization.role)) {
          window.location.replace(routeAvailability?.unavailableRedirect ?? "/app");
          return;
        }
        setProfile(session);
        setSessionIssue(null);
        setChecking(false);
      } catch (error) {
        if (!active) return;
        if (isAuthenticationRequired(error)) {
          const returnTo = encodeURIComponent(pathname);
          window.location.assign(`/login?returnTo=${returnTo}`);
          return;
        }
        if (attempt < SESSION_RETRY_DELAYS_MS.length) {
          setSessionIssue("Connection interrupted. Reconnecting your session...");
          retryTimer = window.setTimeout(
            () => void loadSession(attempt + 1),
            SESSION_RETRY_DELAYS_MS[attempt],
          );
          return;
        }
        setSessionIssue("We could not verify your session. Your sign-in was not cleared.");
        setChecking(false);
      }
    }

    void loadSession(0);
    return () => {
      active = false;
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
    };
  }, [isPublic, pathname, profile, routeAvailability, sessionRetryKey]);

  useEffect(() => {
    if (isPublic || !profile) return;
    if (!routeEnabled && routeAvailability) {
      window.location.replace(routeAvailability.unavailableRedirect);
      return;
    }
    if (!isRouteAvailable(pathname, profile.organization.role)) {
      window.location.replace(routeAvailability?.unavailableRedirect ?? "/app");
    }
  }, [isPublic, pathname, profile, routeAvailability, routeEnabled]);

  useEffect(() => {
    if (isPublic || !sessionId) return;
    let active = true;
    let inFlight = false;

    async function revalidateSession() {
      if (inFlight) return;
      inFlight = true;
      try {
        const session = await getAccountSession();
        if (!active) return;
        setProfile(session);
        setSessionIssue(null);
      } catch (error) {
        if (!active) return;
        if (isAuthenticationRequired(error)) {
          const returnTo = encodeURIComponent(window.location.pathname);
          window.location.assign(`/login?returnTo=${returnTo}`);
          return;
        }
        setSessionIssue("Connection interrupted. Your session remains open while we retry.");
      } finally {
        inFlight = false;
      }
    }

    const interval = window.setInterval(() => void revalidateSession(), SESSION_REVALIDATION_MS);
    function handleVisibilityChange() {
      if (document.visibilityState === "visible") void revalidateSession();
    }
    document.addEventListener("visibilitychange", handleVisibilityChange);
    if (sessionRetryKey > 0) void revalidateSession();
    return () => {
      active = false;
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [isPublic, sessionId, sessionRetryKey]);

  useEffect(() => {
    function openCommandPalette(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandPaletteOpen(true);
      }
    }
    window.addEventListener("keydown", openCommandPalette);
    return () => window.removeEventListener("keydown", openCommandPalette);
  }, []);

  if (isPublic) return <>{children}</>;

  if (checking || !profile) {
    return (
      <main className="grid min-h-screen place-items-center bg-fog px-6 text-ink">
        <div className="text-center">
          {checking ? (
            <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-teal/25 border-t-teal" />
          ) : null}
          <p className="mt-4 text-sm text-ink/65">
            {sessionIssue ?? "Opening your decision workspace…"}
          </p>
          {!checking && sessionIssue ? (
            <button
              type="button"
              onClick={() => setSessionRetryKey((value) => value + 1)}
              className="focus-ring mx-auto mt-4 inline-flex items-center gap-2 rounded-md border border-line px-4 py-2 text-sm text-ink/80"
            >
              <RefreshCw className="h-4 w-4" /> Retry session check
            </button>
          ) : null}
        </div>
      </main>
    );
  }

  const navItems = NAV_ITEMS.filter((item) => isRouteAvailable(item.href, profile.organization.role));

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
            <button
              type="button"
              onClick={() => setCommandPaletteOpen(true)}
              className="focus-ring mt-3 flex w-full items-center justify-between rounded-md border border-line px-2 py-2 text-xs text-ink/65"
            >
              <span className="inline-flex items-center gap-2"><Search className="h-3.5 w-3.5" /> Commands</span>
              <span>Ctrl K</span>
            </button>
          </section>
        </aside>

        <main className="min-h-screen min-w-0 flex-1 p-4 pb-24 lg:p-8 lg:pb-8">
          {sessionIssue ? (
            <div className="mb-4 flex items-center justify-between gap-4 rounded-md border border-amber-300/30 bg-amber-300/10 px-4 py-3 text-sm text-ink/80" role="status">
              <span>{sessionIssue}</span>
              <button
                type="button"
                onClick={() => setSessionRetryKey((value) => value + 1)}
                className="focus-ring shrink-0 rounded-md p-2 text-ink/70 hover:bg-white/5 hover:text-ink"
                aria-label="Retry session check"
              >
                <RefreshCw className="h-4 w-4" />
              </button>
            </div>
          ) : null}
          {children}
        </main>
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
      <CommandPalette
        open={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
        role={profile.organization.role}
      />
    </div>
  );
}
