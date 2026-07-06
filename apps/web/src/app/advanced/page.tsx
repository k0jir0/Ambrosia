import Link from "next/link";
import { Badge, Panel, SectionTitle } from "@/components/ui";

type ModuleRoute = {
  title: string;
  eyebrow: string;
  description: string;
  href: string;
  destination: string;
  panels: string;
};

const MODULE_ROUTES: ModuleRoute[] = [
  {
    title: "Calibration & Feedback",
    eyebrow: "Quality Loop",
    description: "Confidence bands, cohort diagnostics, anomaly visibility, and outcome recording.",
    href: "/calibration",
    destination: "Calibration",
    panels: "7 panels"
  },
  {
    title: "Team Collaboration",
    eyebrow: "Governance",
    description: "Workspace management, packet sharing, comments, and approval workflow proof.",
    href: "/team",
    destination: "Team",
    panels: "4 panels"
  },
  {
    title: "Workflow Templates",
    eyebrow: "Marketplace",
    description: "Template browse, create, publish, archive, and version-management surfaces.",
    href: "/team",
    destination: "Team",
    panels: "3 panels"
  },
  {
    title: "Admin & Monitoring",
    eyebrow: "Default Proof Surface",
    description: "System health, provider status, tool boundaries, alerts, and certification gates.",
    href: "/admin",
    destination: "Admin",
    panels: "6 panels"
  },
  {
    title: "Provider Modes",
    eyebrow: "Runtime",
    description: "Local, hosted, and hybrid provider-path visibility for platform operators.",
    href: "/platform",
    destination: "Platform",
    panels: "1 panel"
  },
  {
    title: "Async Jobs",
    eyebrow: "Execution Queue",
    description: "Background scanner, backtest, and report job controls with progress visibility.",
    href: "/execution-intelligence",
    destination: "Execution Intelligence",
    panels: "3 panels"
  },
  {
    title: "Archive & Search",
    eyebrow: "Decision Memory",
    description: "Packet and review lookup surfaces for reusable, searchable, auditable history.",
    href: "/history",
    destination: "History",
    panels: "2 panels"
  }
];

export default function AdvancedPage() {
  return (
    <div className="space-y-4">
      <Panel className="p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <SectionTitle eyebrow="Advanced" title="Module directory" />
            <p className="mt-3 max-w-4xl text-sm leading-6 text-ink/75">
              The advanced inventory has been moved into the route where each module belongs. Use this page as a
              cross-surface index when you need to jump between operator, team, calibration, execution, and history views.
            </p>
          </div>
          <Badge tone="info">26 panels / 7 destinations</Badge>
        </div>
      </Panel>

      <section className="grid gap-4 xl:grid-cols-2">
        {MODULE_ROUTES.map((route) => (
          <Link
            key={`${route.title}-${route.href}`}
            href={route.href}
            className="focus-ring rounded-lg border border-line bg-paper p-5 transition hover:border-teal/50"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-teal">{route.eyebrow}</p>
                <h2 className="text-base font-semibold text-ink">{route.title}</h2>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-ink/70">{route.description}</p>
              </div>
              <Badge tone="neutral">{route.panels}</Badge>
            </div>
            <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-ink/50">Moved to {route.destination}</p>
          </Link>
        ))}
      </section>
    </div>
  );
}
