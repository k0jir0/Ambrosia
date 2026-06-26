import { Badge, Panel, SectionTitle } from "@/components/ui";

const ADVANCED_SURFACES = [
  {
    title: "Operational Health",
    description: "Health checks, provider status, scorecard, function registry, and visibility matrix coverage.",
    endpoints: ["GET /health/detailed", "GET /providers/status", "GET /visibility/frontend-matrix"]
  },
  {
    title: "Alerts And Calibration",
    description: "Mobile alert events, alert subscriptions, calibration cohorts, calibration bands, and feedback records.",
    endpoints: ["GET /alerts/mobile", "POST /alerts/subscriptions", "GET /feedback/calibration/summary"]
  },
  {
    title: "Scanner And Sandbox",
    description: "Async scanner jobs, sandbox orders, sandbox positions, and market-provider status.",
    endpoints: ["POST /scanner/run", "POST /sandbox/orders/simulate", "GET /sandbox/positions"]
  },
  {
    title: "Attribution",
    description: "Packet attribution compute and latest attribution reports for post-decision learning.",
    endpoints: ["POST /packets/{packet_id}/attribution/compute", "GET /packets/{packet_id}/attribution/latest"]
  }
];

export default function AdvancedPage() {
  return (
    <div className="space-y-4">
      <Panel className="p-6">
        <SectionTitle eyebrow="Advanced" title="Operator and instrumentation surface" />
        <p className="mt-3 max-w-4xl text-sm leading-6 text-ink/75">
          This surface gathers the non-admin power-user functions that support Ambrosia production workflow:
          observability, calibration, alerts, scanner jobs, sandbox execution, and attribution. These controls are
          mapped in the visibility matrix as analyst-level routes, separate from admin-only policy and template controls.
        </p>
      </Panel>

      <section className="grid gap-4 xl:grid-cols-2">
        {ADVANCED_SURFACES.map((surface) => (
          <Panel key={surface.title} className="p-5">
            <div className="flex items-start justify-between gap-3">
              <SectionTitle eyebrow="Analyst" title={surface.title} />
              <Badge tone="info">/advanced</Badge>
            </div>
            <p className="mt-3 text-sm leading-6 text-ink/70">{surface.description}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {surface.endpoints.map((endpoint) => (
                <span key={endpoint} className="rounded-md border border-line bg-fog px-2 py-1 text-xs text-ink/70">
                  {endpoint}
                </span>
              ))}
            </div>
          </Panel>
        ))}
      </section>
    </div>
  );
}
