import { Panel, SectionTitle } from "@/components/ui";

const CLI_PILLARS = [
  {
    title: "API-first contract",
    detail: "The CLI maps typed commands to stable API routes so automation, SDK, and web control-plane semantics stay aligned."
  },
  {
    title: "Safe automation defaults",
    detail: "JSON output, profile-based auth, explicit timeouts, and clear scope flags support CI and operator workflows."
  },
  {
    title: "Operational module coverage",
    detail: "Command families span relay, alpha, backtests, paper-trades, warm-path intelligence, and enterprise governance."
  },
  {
    title: "Distribution and provenance",
    detail: "CLI packaging includes Python distribution and container release flow with checksums and signed artifact evidence."
  }
];

const CLI_FAMILIES = [
  "auth / config / health",
  "reviews / packets / market / scanner / jobs / plans",
  "relay / signals / alpha / backtests",
  "paper-trades / warm-path",
  "enterprise"
];

const CLI_FLOW = [
  {
    stage: "1) Bootstrap and identity",
    goal: "Establish API target, profile, and caller identity before doing stateful work.",
    commands: [
      "ambrosia auth login",
      "ambrosia auth whoami",
      "ambrosia config get api_url",
      "ambrosia --json health --detailed"
    ],
    endpoints: ["/health", "/health/detailed"]
  },
  {
    stage: "2) Decision intake and packet access",
    goal: "Create or load review and packet context to anchor the decision workflow.",
    commands: [
      "ambrosia --json reviews create --thesis \"...\" --ticker SOXX",
      "ambrosia --json reviews list",
      "ambrosia --json packets get <packet_id>",
      "ambrosia --json market snapshot SOXX"
    ],
    endpoints: ["/reviews", "/packets/{id}", "/market/{ticker}/snapshot"]
  },
  {
    stage: "3) Research and relay",
    goal: "Run financial reasoning through relay and create structured alpha/signal objects.",
    commands: [
      "ambrosia --json relay evaluate --question \"What evidence supports margin expansion?\"",
      "ambrosia --json signals create --name Momentum --formula \"close/close_20d-1\"",
      "ambrosia --json alpha create --title \"Momentum persistence\" --signal-family momentum --thesis \"...\"",
      "ambrosia --json alpha list"
    ],
    endpoints: ["/relay/evaluate", "/signals", "/alpha/hypotheses"]
  },
  {
    stage: "4) Validation and execution intelligence",
    goal: "Move from hypothesis to validation with backtests and warm-path diagnostics.",
    commands: [
      "ambrosia --json backtests run --signal-id <signal_id>",
      "ambrosia --json alpha decay --signal-id <signal_id>",
      "ambrosia --json paper-trades create --decision-id <id> --ticker SOXX --quantity 1",
      "ambrosia --json warm-path ingest --event-type fill --ticker SOXX --latency-ms 123 --notional-usd 12500",
      "ambrosia --json warm-path list"
    ],
    endpoints: ["/backtests/run", "/signals/{id}/alpha-decay", "/paper-trades", "/execution/warm-path/events"]
  },
  {
    stage: "5) Enterprise governance",
    goal: "Manage enterprise lifecycle controls, readiness, and security packet retrieval.",
    commands: [
      "ambrosia --json enterprise service-account --name ci-bot --scopes public:read,advanced:read",
      "ambrosia --json enterprise service-account-rotate <service_account_id>",
      "ambrosia --json enterprise audit-export --requested-by admin --scope all",
      "ambrosia --json enterprise sso-config --provider oidc --issuer-url <url> --audience ambrosia-enterprise",
      "ambrosia --json enterprise readiness",
      "ambrosia --json enterprise security-packet"
    ],
    endpoints: ["/enterprise/service-accounts", "/enterprise/audit-exports", "/enterprise/sso/config", "/enterprise/readiness", "/enterprise/support/security-packet"]
  }
];

export default function CliDesignPage() {
  return (
    <div className="space-y-4">
      <Panel className="p-6">
        <SectionTitle eyebrow="Index84 Surface" title="CLI Design" />
        <p className="mt-3 max-w-3xl text-sm text-ink/75">
          Ambrosia CLI is designed as a programmable operator interface over the same platform contracts used by SDK and web control-plane modules.
        </p>
      </Panel>

      <Panel className="p-6">
        <SectionTitle eyebrow="Design Pillars" title="Why the CLI exists" />
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {CLI_PILLARS.map((pillar) => (
            <div key={pillar.title} className="rounded-md border border-line bg-fog/70 p-4 text-sm">
              <p className="font-semibold text-ink">{pillar.title}</p>
              <p className="mt-2 text-ink/70">{pillar.detail}</p>
            </div>
          ))}
        </div>
      </Panel>

      <Panel className="p-6">
        <SectionTitle eyebrow="Command Surface" title="Current families" />
        <ul className="mt-3 space-y-2 text-sm text-ink/75">
          {CLI_FAMILIES.map((family) => (
            <li key={family} className="rounded-md border border-line bg-fog/70 px-3 py-2">
              {family}
            </li>
          ))}
        </ul>
      </Panel>

      <Panel className="p-6">
        <SectionTitle eyebrow="End-to-End Flow" title="Entire CLI function flow" />
        <div className="mt-4 space-y-4">
          {CLI_FLOW.map((flow) => (
            <div key={flow.stage} className="rounded-md border border-line bg-fog/70 p-4">
              <p className="text-sm font-semibold text-ink">{flow.stage}</p>
              <p className="mt-1 text-sm text-ink/70">{flow.goal}</p>
              <div className="mt-3 grid gap-3 xl:grid-cols-2">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-teal">Commands</p>
                  <ul className="mt-2 space-y-1 text-xs text-ink/80">
                    {flow.commands.map((command) => (
                      <li key={command} className="rounded border border-line bg-paper/70 px-2 py-1 font-mono">
                        {command}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-teal">Route contracts</p>
                  <ul className="mt-2 space-y-1 text-xs text-ink/80">
                    {flow.endpoints.map((endpoint) => (
                      <li key={endpoint} className="rounded border border-line bg-paper/70 px-2 py-1 font-mono">
                        {endpoint}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
