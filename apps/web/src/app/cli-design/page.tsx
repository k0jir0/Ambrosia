import { Badge, Panel, SectionTitle } from "@/components/ui";

const CLI_PILLARS = [
  {
    title: "Install once",
    detail: "Ambrosia should be installed into a local shell once, then run from any terminal as the ambrosia executable."
  },
  {
    title: "Discover locally",
    detail: "Operators should reach ambrosia --help, ambrosia commands list, and numbered command details without knowing repo layout."
  },
  {
    title: "Script cleanly",
    detail: "Human output remains readable by default, while --json produces stable machine-readable payloads for automation."
  },
  {
    title: "Share one contract",
    detail: "The CLI maps to SDK methods, and the SDK wraps the API so every operator path stays aligned with platform contracts."
  }
];

const ARCHITECTURE_LAYERS = [
  {
    layer: "API",
    purpose: "Authoritative network contract with stable routes, validation, auth, versioned lifecycle objects, and structured errors.",
    examples: ["/reviews", "/scanner/run", "/signals", "/alpha/hypotheses", "/enterprise/readiness"]
  },
  {
    layer: "SDK",
    purpose: "Thin Python wrapper around API concepts, using predictable methods before higher-level workflow helpers are added.",
    examples: ["health()", "create_review(...)", "scanner_run(...)", "list_signals()", "create_paper_trade(...)"]
  },
  {
    layer: "CLI",
    purpose: "Accessible operator shell over the SDK, with noun-verb commands, local discovery, JSON mode, and automation flags.",
    examples: ["ambrosia health", "ambrosia scanner run", "ambrosia signals list", "ambrosia enterprise readiness"]
  }
];

const INSTALL_PATHS = [
  {
    title: "Developer editable install",
    commands: ["cd Ambrosia/packages/cli", "uv pip install -e ../sdk-python", "uv pip install -e .", "ambrosia commands list"],
    note: "Works today and should remain documented for contributors."
  },
  {
    title: "Future packaged install",
    commands: ["pipx install ambrosia-cli", "uv tool install ./packages/cli", "ambrosia --help"],
    note: "Target experience once CLI packaging declares its SDK dependency cleanly."
  },
  {
    title: "Windows operator launcher",
    commands: ["launch-ambrosia-cli-menu.bat", "ambrosia commands list"],
    note: "A double-click bridge for local Windows use, complementary to PATH-based shell access."
  }
];

const COMMAND_EXAMPLES = [
  "ambrosia health",
  "ambrosia scanner run --universe AAPL,MSFT,SPY --max-candidates 5",
  "ambrosia signals list",
  "ambrosia signals create --name Momentum --formula \"close/close_20d-1\"",
  "ambrosia signals writeback-decision --signal-id signal-1 --review-id review-1 --decision-state pursue",
  "ambrosia alpha list",
  "ambrosia paper-trades list --limit 20",
  "ambrosia enterprise readiness"
];

const DISCOVERY_COMMANDS = ["ambrosia --help", "ambrosia <resource> --help", "ambrosia commands list", "ambrosia commands show <index>"];

const OUTPUT_MODES = [
  { mode: "Human default", example: "ambrosia signals list", purpose: "Readable terminal summaries for interactive use." },
  { mode: "Machine mode", example: "ambrosia --json signals list", purpose: "Stable JSON output for scripts, CI, and higher-level automation." },
  { mode: "Future modes", example: "--table, --plain, --output path", purpose: "Compact tables, line-oriented output, and generated file destinations." }
];

const CONFIG_PRIORITY = ["Explicit flags", "Environment variables", "Profile config", "Default local URL"];

const ERROR_RULES = [
  "API unavailable",
  "Invalid token",
  "Missing required flag",
  "Endpoint returned non-JSON response",
  "Validation failed"
];

const SDK_METHODS = [
  "health()",
  "list_reviews()",
  "create_review(...)",
  "scanner_run(...)",
  "list_signals()",
  "create_signal(...)",
  "writeback_signal_decision(...)",
  "run_backtest(...)",
  "list_alpha_hypotheses(...)",
  "create_paper_trade(...)",
  "list_service_accounts(...)"
];

const TYPED_PAYLOADS = [
  "ReviewCreate",
  "SignalCreate",
  "SignalDecisionWriteback",
  "SignalOutcomeWriteback",
  "AlphaHypothesisCreate",
  "PaperTradeCreate"
];

const API_REQUIREMENTS = [
  "Stable route names",
  "Consistent JSON request and response bodies",
  "Consistent error envelope",
  "Idempotency keys for writes",
  "Versioned lifecycle objects",
  "OpenAPI artifacts generated and checked in CI"
];

const COMPLIANCE = [
  { item: "Single executable", state: "Pass" },
  { item: "Noun-verb subcommands", state: "Pass" },
  { item: "Argparse help", state: "Pass" },
  { item: "Numbered command menu", state: "Pass" },
  { item: "Persistent Windows launcher", state: "Pass" },
  { item: "JSON output", state: "Pass" },
  { item: "API URL and token configuration", state: "Pass" },
  { item: "SDK wrapper", state: "Pass" },
  { item: "One-step local install", state: "Partial" },
  { item: "SDK dependency declared in CLI package", state: "Needs improvement" },
  { item: "PATH/global shell install documented", state: "Needs improvement" },
  { item: "Typed SDK payload models", state: "Needs improvement" },
  { item: "Secret handling beyond env/flags", state: "Needs improvement" }
];

const ROADMAP = [
  {
    phase: "Phase 1",
    title: "Make local install reliable",
    items: ["Add SDK dependency declaration to CLI package.", "Add a root cli:menu script.", "Document uv and pipx installation."]
  },
  {
    phase: "Phase 2",
    title: "Make shell access first-class",
    items: ["Provide a Windows PowerShell install script.", "Offer an optional PATH setup helper.", "Add ambrosia --version."]
  },
  {
    phase: "Phase 3",
    title: "Improve discoverability",
    items: ["Improve top-level help with examples.", "Add ambrosia examples or quickstart.", "Group command catalog by domain."]
  },
  {
    phase: "Phase 4",
    title: "Strengthen SDK types",
    items: ["Add typed payload models for common objects.", "Keep a dict escape hatch.", "Match SDK examples to CLI groups."]
  },
  {
    phase: "Phase 5",
    title: "Contract coverage",
    items: ["Expose or mark every public API route.", "Maintain route inventory, SDK/CLI smoke tests, and visibility matrix checks."]
  }
];

const OPERATOR_FLOW = [
  "Double-click launch-ambrosia-cli-menu.bat.",
  "See the command menu.",
  "Inspect a numbered command.",
  "Run health --detailed or signals list.",
  "Quit with Q."
];

const DEVELOPER_FLOW = [
  "Install with pipx or uv.",
  "Open any shell.",
  "Run ambrosia commands list.",
  "Pipe ambrosia --json signals list into tooling."
];

const PYTHON_EXAMPLE = [
  "from ambrosia_sdk import AmbrosiaClient",
  "client = AmbrosiaClient(base_url=\"https://ambrosia-api-staging.onrender.com\")",
  "signals = client.list_signals()"
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
        <SectionTitle eyebrow="Index100 Surface" title="CLI Design" />
        <p className="mt-3 max-w-3xl text-sm text-ink/75">
          Toward an industry-standard Ambrosia CLI and SDK surface: the API is authoritative, the SDK is the typed programmable wrapper, and the CLI is the accessible operator shell.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Badge tone="good">Single executable</Badge>
          <Badge tone="good">Noun-verb commands</Badge>
          <Badge tone="info">SDK aligned</Badge>
          <Badge tone="warn">Packaging next</Badge>
        </div>
      </Panel>

      <Panel className="p-6">
        <SectionTitle eyebrow="Goal" title="Local operator surface" />
        <p className="mt-3 max-w-4xl text-sm leading-6 text-ink/75">
          The CLI should be more than a developer convenience. A user should install Ambrosia once, configure base URL and credentials once, discover commands locally, use readable output interactively, switch to JSON for scripts, and call the same platform capabilities through the Python SDK.
        </p>
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
        <SectionTitle eyebrow="Reference Pattern" title="API + SDK + CLI triangle" />
        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          {ARCHITECTURE_LAYERS.map((layer) => (
            <div key={layer.layer} className="rounded-md border border-line bg-fog/70 p-4 text-sm">
              <p className="font-semibold text-ink">{layer.layer}</p>
              <p className="mt-2 leading-6 text-ink/70">{layer.purpose}</p>
              <ul className="mt-3 space-y-1 text-xs text-ink/75">
                {layer.examples.map((example) => (
                  <li key={example} className="rounded border border-line bg-paper/70 px-2 py-1 font-mono">
                    {example}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Panel>

      <Panel className="p-6">
        <SectionTitle eyebrow="Audit" title="Current Ambrosia CLI posture" />
        <div className="mt-4 grid gap-3 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="rounded-md border border-line bg-fog/70 p-4 text-sm">
            <p className="font-semibold text-ink">Already aligned</p>
            <p className="mt-2 leading-6 text-ink/70">
              Ambrosia already has the important shape: one ambrosia executable, noun-first command groups, verb subcommands, --json, --api-url, --token, --timeout, quiet/verbose flags, and command discovery through ambrosia commands list.
            </p>
          </div>
          <div className="rounded-md border border-amber/30 bg-amber/10 p-4 text-sm">
            <p className="font-semibold text-amber">Main gap</p>
            <p className="mt-2 leading-6 text-ink/75">
              Accessibility is primarily a packaging issue. The CLI package should declare the SDK dependency so a fresh install is self-contained, then place ambrosia on PATH through pipx, uv tool, or an installer.
            </p>
          </div>
        </div>
      </Panel>

      <Panel className="p-6">
        <SectionTitle eyebrow="Installation" title="Recommended local access paths" />
        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          {INSTALL_PATHS.map((path) => (
            <div key={path.title} className="rounded-md border border-line bg-fog/70 p-4">
              <p className="text-sm font-semibold text-ink">{path.title}</p>
              <ul className="mt-3 space-y-1 text-xs text-ink/80">
                {path.commands.map((command) => (
                  <li key={command} className="rounded border border-line bg-paper/70 px-2 py-1 font-mono">
                    {command}
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-xs leading-5 text-ink/65">{path.note}</p>
            </div>
          ))}
        </div>
      </Panel>

      <section className="grid gap-4 xl:grid-cols-2">
        <Panel className="p-6">
          <SectionTitle eyebrow="Command Shape" title="Predictable noun-verb surface" />
          <p className="mt-3 text-sm leading-6 text-ink/70">
            Ambrosia should keep ambrosia &lt;resource&gt; &lt;action&gt; [flags] as its public command grammar because it is guessable, extensible, and maps naturally to API resource groups.
          </p>
          <ul className="mt-4 space-y-1 text-xs text-ink/80">
            {COMMAND_EXAMPLES.map((command) => (
              <li key={command} className="rounded border border-line bg-fog/70 px-2 py-1 font-mono">
                {command}
              </li>
            ))}
          </ul>
        </Panel>

        <Panel className="p-6">
          <SectionTitle eyebrow="Discovery" title="Help and command catalog" />
          <p className="mt-3 text-sm leading-6 text-ink/70">
            The numbered catalog should remain a core Ambrosia affordance: it works like a local function menu without forcing a full-screen terminal UI.
          </p>
          <ul className="mt-4 grid gap-2 text-xs text-ink/80 md:grid-cols-2">
            {DISCOVERY_COMMANDS.map((command) => (
              <li key={command} className="rounded border border-line bg-fog/70 px-2 py-2 font-mono">
                {command}
              </li>
            ))}
          </ul>
        </Panel>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Panel className="p-6">
          <SectionTitle eyebrow="Output" title="Human by default, JSON for machines" />
          <div className="mt-4 space-y-3">
            {OUTPUT_MODES.map((output) => (
              <div key={output.mode} className="rounded-md border border-line bg-fog/70 p-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-semibold text-ink">{output.mode}</p>
                  <code className="rounded border border-line bg-paper/70 px-2 py-1 text-xs text-ink/80">{output.example}</code>
                </div>
                <p className="mt-2 text-ink/70">{output.purpose}</p>
              </div>
            ))}
          </div>
        </Panel>

        <Panel className="p-6">
          <SectionTitle eyebrow="Configuration" title="Precedence and secret handling" />
          <ol className="mt-4 space-y-2 text-sm text-ink/75">
            {CONFIG_PRIORITY.map((item, index) => (
              <li key={item} className="rounded-md border border-line bg-fog/70 px-3 py-2">
                <span className="mr-2 font-semibold text-teal">{index + 1}.</span>
                {item}
              </li>
            ))}
          </ol>
          <p className="mt-4 text-sm leading-6 text-ink/70">
            Tokens should move beyond flags and environment variables over time. The target is secure local credential storage, token presence checks that do not reveal the token, and --token-file for automation.
          </p>
        </Panel>
      </section>

      <Panel className="p-6">
        <SectionTitle eyebrow="Errors" title="Readable operator failures" />
        <p className="mt-3 max-w-4xl text-sm leading-6 text-ink/70">
          Normal CLI use should not show raw stack traces for expected problems. AmbrosiaApiError is the right foundation; these cases should become structured human messages and JSON errors.
        </p>
        <ul className="mt-4 grid gap-2 text-sm text-ink/75 md:grid-cols-2 xl:grid-cols-5">
          {ERROR_RULES.map((rule) => (
            <li key={rule} className="rounded-md border border-line bg-fog/70 px-3 py-2">
              {rule}
            </li>
          ))}
        </ul>
      </Panel>

      <section className="grid gap-4 xl:grid-cols-2">
        <Panel className="p-6">
          <SectionTitle eyebrow="SDK" title="Thin wrapper with typed payloads" />
          <p className="mt-3 text-sm leading-6 text-ink/70">
            The SDK should map one method to one platform capability, keeping resource semantics visible and avoiding magic workflow helpers as the stable base.
          </p>
          <ul className="mt-4 grid gap-2 text-xs text-ink/80 md:grid-cols-2">
            {SDK_METHODS.map((method) => (
              <li key={method} className="rounded border border-line bg-fog/70 px-2 py-2 font-mono">
                {method}
              </li>
            ))}
          </ul>
        </Panel>

        <Panel className="p-6">
          <SectionTitle eyebrow="Types" title="Payload helpers to add next" />
          <p className="mt-3 text-sm leading-6 text-ink/70">
            The current dict-based SDK is flexible. Typed helpers should reduce user error while preserving a raw escape hatch for newly added API surfaces.
          </p>
          <ul className="mt-4 grid gap-2 text-sm text-ink/75 md:grid-cols-2">
            {TYPED_PAYLOADS.map((payload) => (
              <li key={payload} className="rounded-md border border-line bg-fog/70 px-3 py-2 font-mono text-xs">
                {payload}
              </li>
            ))}
          </ul>
        </Panel>
      </section>

      <Panel className="p-6">
        <SectionTitle eyebrow="API" title="Source of truth requirements" />
        <ul className="mt-4 grid gap-2 text-sm text-ink/75 md:grid-cols-2 xl:grid-cols-3">
          {API_REQUIREMENTS.map((requirement) => (
            <li key={requirement} className="rounded-md border border-line bg-fog/70 px-3 py-2">
              {requirement}
            </li>
          ))}
        </ul>
      </Panel>

      <Panel className="p-6">
        <SectionTitle eyebrow="Compliance" title="Index100 assessment" />
        <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {COMPLIANCE.map((row) => (
            <div key={row.item} className="flex items-center justify-between gap-3 rounded-md border border-line bg-fog/70 px-3 py-2 text-sm">
              <span className="text-ink/75">{row.item}</span>
              <Badge tone={badgeTone(row.state)}>{row.state}</Badge>
            </div>
          ))}
        </div>
      </Panel>

      <Panel className="p-6">
        <SectionTitle eyebrow="Roadmap" title="Productize without redesigning" />
        <div className="mt-4 grid gap-3 xl:grid-cols-5">
          {ROADMAP.map((phase) => (
            <div key={phase.phase} className="rounded-md border border-line bg-fog/70 p-4 text-sm">
              <p className="text-xs font-semibold uppercase tracking-wide text-teal">{phase.phase}</p>
              <p className="mt-1 font-semibold text-ink">{phase.title}</p>
              <ul className="mt-3 space-y-2 text-xs leading-5 text-ink/70">
                {phase.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
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

      <section className="grid gap-4 xl:grid-cols-3">
        <Panel className="p-6">
          <SectionTitle eyebrow="Windows" title="Operator flow" />
          <NumberedList items={OPERATOR_FLOW} />
        </Panel>
        <Panel className="p-6">
          <SectionTitle eyebrow="Developer" title="Shell flow" />
          <NumberedList items={DEVELOPER_FLOW} />
        </Panel>
        <Panel className="p-6">
          <SectionTitle eyebrow="Python" title="SDK flow" />
          <ul className="mt-4 space-y-1 text-xs text-ink/80">
            {PYTHON_EXAMPLE.map((line) => (
              <li key={line} className="rounded border border-line bg-fog/70 px-2 py-2 font-mono">
                {line}
              </li>
            ))}
          </ul>
        </Panel>
      </section>

      <Panel className="p-6">
        <SectionTitle eyebrow="Recommendation" title="Standardize the triangle" />
        <p className="mt-3 max-w-4xl text-sm leading-6 text-ink/75">
          Ambrosia should keep the current CLI architecture and focus the next work on productization: declare dependencies cleanly, put ambrosia on PATH, document install flows, add typed SDK payloads, preserve the command catalog, and keep CLI, SDK, and API coverage checked in CI.
        </p>
        <p className="mt-3 text-xs text-ink/55">
          Research basis: Command Line Interface Guidelines, POSIX utility conventions, Azure CLI guidance, AWS CLI guidance, and the local Ambrosia repository audit in index100.txt.
        </p>
      </Panel>
    </div>
  );
}

function badgeTone(state: string): "neutral" | "good" | "warn" | "bad" | "info" {
  if (state === "Pass") return "good";
  if (state === "Partial") return "warn";
  if (state === "Needs improvement") return "bad";
  return "neutral";
}

function NumberedList({ items }: { items: string[] }) {
  return (
    <ol className="mt-4 space-y-2 text-sm text-ink/75">
      {items.map((item, index) => (
        <li key={item} className="rounded-md border border-line bg-fog/70 px-3 py-2">
          <span className="mr-2 font-semibold text-teal">{index + 1}.</span>
          {item}
        </li>
      ))}
    </ol>
  );
}
