"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Activity, BarChart3, Binary, Building2, ClipboardPlus, Command, FlaskConical, Gauge, History, Home, Layers3, Radar, Settings, SlidersHorizontal, TerminalSquare, Users } from "lucide-react";
import { cn } from "./ui";
import { CommandPalette } from "./command-palette";

type NavItem = {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  group: "top" | "middle" | "bottom";
};

const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Dashboard", icon: Home, group: "top" },
  { href: "/review/new", label: "New Review", icon: ClipboardPlus, group: "top" },
  { href: "/markets/AAPL", label: "Market Intelligence", icon: Activity, group: "middle" },
  { href: "/alpha", label: "Alpha Lab", icon: FlaskConical, group: "middle" },
  { href: "/execution-intelligence", label: "Execution Intelligence", icon: Radar, group: "middle" },
  { href: "/history", label: "Decision History", icon: History, group: "middle" },
  { href: "/calibration", label: "Calibration", icon: BarChart3, group: "middle" },
  { href: "/relay-benchmarks", label: "Relay + Benchmarks", icon: Binary, group: "middle" },
  { href: "/cli-design", label: "CLI Design", icon: TerminalSquare, group: "middle" },
  { href: "/enterprise", label: "Enterprise", icon: Building2, group: "bottom" },
  { href: "/team", label: "Team", icon: Users, group: "bottom" },
  { href: "/admin", label: "Admin", icon: Settings, group: "bottom" },
  { href: "/advanced", label: "Advanced", icon: SlidersHorizontal, group: "bottom" },
  { href: "/platform", label: "Platform", icon: Layers3, group: "bottom" }
];

const MOBILE_ITEMS = [
  { href: "/", label: "Dashboard", icon: Home },
  { href: "/review/new", label: "New", icon: ClipboardPlus },
  { href: "/markets/AAPL", label: "Markets", icon: Activity },
  { href: "/history", label: "History", icon: History },
  { href: "/calibration", label: "More", icon: Gauge }
];

function isActivePath(pathname: string | null, href: string) {
  if (!pathname) return href === "/";
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [pathname, setPathname] = useState<string>(typeof window === "undefined" ? "/" : window.location.pathname);
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen(true);
      }
      if (event.key === "Escape") {
        setPaletteOpen(false);
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    function updatePath() {
      setPathname(window.location.pathname);
    }

    updatePath();
    window.addEventListener("popstate", updatePath);
    window.addEventListener("hashchange", updatePath);

    return () => {
      window.removeEventListener("popstate", updatePath);
      window.removeEventListener("hashchange", updatePath);
    };
  }, []);

  const top = NAV_ITEMS.filter((item) => item.group === "top");
  const middle = NAV_ITEMS.filter((item) => item.group === "middle");
  const bottom = NAV_ITEMS.filter((item) => item.group === "bottom");

  return (
    <div className="min-h-screen bg-fog text-ink">
      <div className="mx-auto flex w-full max-w-[1600px]">
        <aside className="hidden min-h-screen w-64 shrink-0 border-r border-line/80 bg-paper/90 p-4 lg:block">
          <div className="mb-4 flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal">Ambrosia</p>
            <button
              type="button"
              onClick={() => setPaletteOpen(true)}
              className="focus-ring inline-flex items-center gap-1 rounded border border-line px-2 py-1 text-[11px] text-ink/70"
            >
              <Command className="h-3.5 w-3.5" /> K
            </button>
          </div>
          <div className="space-y-6">
            <NavSection items={top} pathname={pathname} />
            <NavSection items={middle} pathname={pathname} />
            <NavSection items={bottom} pathname={pathname} />
            <OperatingModelPanel />
          </div>
        </aside>

        <main className="min-h-screen flex-1 p-4 pb-24 lg:p-8 lg:pb-8">{children}</main>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-paper/95 p-2 backdrop-blur lg:hidden">
        <ul className="grid grid-cols-5 gap-1">
          {MOBILE_ITEMS.map((item) => {
            const active = isActivePath(pathname, item.href);
            const Icon = item.icon;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "focus-ring flex flex-col items-center gap-1 rounded-md px-2 py-2 text-[11px] font-medium transition",
                    active ? "bg-teal/15 text-teal" : "text-ink/75 hover:bg-white/5"
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

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}

function OperatingModelPanel() {
  return (
    <section className="rounded-lg border border-line bg-fog/70 p-3 text-[11px] leading-5 text-ink/70">
      <p className="text-xs font-semibold uppercase tracking-wide text-teal">Operating Model</p>
      <div className="mt-2 space-y-2">
        <p>
          <span className="font-semibold text-ink">Agentic AI for Investments:</span> Ambrosia turns a raw thesis into a stateful workflow with intake, retrieval, market context, critique, validation, confidence, audit, and outcome memory.
        </p>
        <p>
          <span className="font-semibold text-ink">Investment Trading Decisions:</span> every review is structured around the human choice to pursue, watch, reject, or request more data before capital is put at risk.
        </p>
        <p>
          <span className="font-semibold text-ink">Swarm Intelligence:</span> specialist lenses like market data, technicals, sentiment, bear case, risk, and synthesis work together instead of relying on one generic answer.
        </p>
        <p>
          <span className="font-semibold text-ink">Agentic Swarm:</span> those specialist lenses participate in a coordinated packet workflow, producing bounded outputs that improve the decision surface.
        </p>
      </div>
    </section>
  );
}

function NavSection({ items, pathname }: { items: NavItem[]; pathname: string }) {
  return (
    <ul className="space-y-1">
      {items.map((item) => {
        const active = isActivePath(pathname, item.href);
        const Icon = item.icon;
        return (
          <li key={item.href}>
            <Link
              href={item.href}
              className={cn(
                "focus-ring flex items-center gap-3 rounded-md px-3 py-2 text-sm transition",
                active ? "bg-teal/10 text-teal" : "text-ink/80 hover:bg-white/5 hover:text-ink"
              )}
            >
              <Icon className="h-4 w-4" />
              <span>{item.label}</span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
