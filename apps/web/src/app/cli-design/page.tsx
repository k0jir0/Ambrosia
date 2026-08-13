import registry from "@/generated/cli-guide-registry.json";
import { Badge, Panel, SectionTitle } from "@/components/ui";

type CommandRecord = {
  index: number;
  command: string;
  workflow: string;
  summary: string;
  authority: "read" | "write";
  implementationStatus: "implemented";
  testStatus: "tested" | "not-tested";
  qualificationStatus: "qualified" | "not-qualified";
  endpoint: string | null;
};

const commands = registry as CommandRecord[];
const workflows = Array.from(new Set(commands.map((command) => command.workflow)));

export default function CliGuidePage() {
  const tested = commands.filter((command) => command.testStatus === "tested").length;
  const qualified = commands.filter((command) => command.qualificationStatus === "qualified").length;

  return (
    <div className="space-y-4">
      <Panel className="p-6">
        <SectionTitle eyebrow="Read-only reference" title="CLI Guide" />
        <div className="mt-4 space-y-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">Capability statement</p>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-ink/75">
              Ambrosia CLI is the local operator interface for setup, health checks, review reads, signal workflows,
              alpha execution commands, and enterprise control-plane inspection. It is a real command surface backed by
              the shipped Python parser and verified contract tests, not a placeholder design page.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/60">Current status</p>
            <Badge tone="good">implemented and locally validated</Badge>
            <Badge tone="warn">release-gated</Badge>
          </div>
          <p className="max-w-4xl text-sm leading-6 text-ink/75">
            This catalog is generated from the shipped Python argparse parser. Implemented means the command parses;
            tested means a focused CLI contract test exists; qualified means a read command also matches the current
            OpenAPI path. These states are independent.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Badge tone="info">{commands.length} implemented</Badge>
            <Badge tone="good">{tested} tested</Badge>
            <Badge tone="good">{qualified} qualified reads</Badge>
          </div>
        </div>
      </Panel>

      <Panel className="p-5">
        <SectionTitle eyebrow="What exists today" title="Current product scope" />
        <ul className="mt-3 grid gap-2 text-sm text-ink/75 md:grid-cols-2">
          <li>Health, config, auth, status, and quickstart operations for local and staging setup.</li>
          <li>Review, packet, market, and scanner commands with parser-backed contract routes.</li>
          <li>Signals, alpha, backtest, paper-trade, and warm-path execution workflows.</li>
          <li>Enterprise control-plane inspection for service accounts, readiness, and security packet reads.</li>
        </ul>
      </Panel>

      <Panel className="p-5">
        <SectionTitle eyebrow="What has been validated" title="Evidence in the repo" />
        <ul className="mt-3 grid gap-2 text-sm text-ink/75 md:grid-cols-2">
          <li>The registry is generated from the parser and is used on this page.</li>
          <li>Focused CLI contract tests exist in packages/cli/tests/test_cli_contract.py.</li>
          <li>Read commands are qualified against the current API path when the route is available.</li>
          <li>This page is intentionally read-only; there is no in-browser terminal and no public package publication is claimed.</li>
        </ul>
      </Panel>

      <Panel className="p-5">
        <SectionTitle eyebrow="Remaining release gates" title="Operational status" />
        <ul className="mt-3 grid gap-2 text-sm text-ink/75 md:grid-cols-2">
          <li>Approve the public release gate language before treating the CLI as broadly production-ready.</li>
          <li>Confirm staging deployment reflects the final page and does not show stale design copy.</li>
          <li>Keep the registry and contract tests as the durable evidence source for product claims.</li>
          <li>Separate what is implemented locally from what is production-gated by server policy or deployment status.</li>
        </ul>
      </Panel>

      <Panel className="p-5">
        <SectionTitle eyebrow="Evidence and ownership" title="Responsible completion language" />
        <p className="mt-3 max-w-4xl text-sm leading-6 text-ink/75">
          The CLI is implemented and locally validated under the repo contract. It remains release-gated for broader
          public claims because deployment and operational evidence must be indexed alongside the parser and tests.
          Ownership stays with the Ambrosia engineering and product owners who confirm the final evidence before any
          production-ready label is used.
        </p>
      </Panel>

      <Panel className="p-5">
        <SectionTitle eyebrow="Boundaries" title="What this page does not claim" />
        <ul className="mt-3 grid gap-2 text-sm text-ink/75 md:grid-cols-2">
          <li>Documentation only; there is no in-browser terminal.</li>
          <li>Local source and wheel workflows exist; no public package publication is claimed.</li>
          <li>Write commands are listed for contract accuracy, not enabled by this page.</li>
          <li>Relay and execution capabilities remain controlled by their existing server policies.</li>
        </ul>
      </Panel>

      {workflows.map((workflow) => (
        <Panel key={workflow} className="overflow-hidden p-0">
          <div className="border-b border-line px-5 py-4">
            <h2 className="text-base font-semibold text-ink">{workflow}</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="bg-fog/70 text-xs text-ink/60">
                <tr>
                  <th className="px-5 py-3 font-medium">Command</th>
                  <th className="px-3 py-3 font-medium">Authority</th>
                  <th className="px-3 py-3 font-medium">Test</th>
                  <th className="px-3 py-3 font-medium">Qualification</th>
                  <th className="px-5 py-3 font-medium">Contract</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {commands.filter((command) => command.workflow === workflow).map((command) => (
                  <tr key={command.command}>
                    <td className="px-5 py-3 font-mono text-xs text-ink">{command.command}</td>
                    <td className="px-3 py-3"><Badge tone={command.authority === "read" ? "info" : "warn"}>{command.authority}</Badge></td>
                    <td className="px-3 py-3">{command.testStatus}</td>
                    <td className="px-3 py-3">{command.qualificationStatus}</td>
                    <td className="px-5 py-3 font-mono text-xs text-ink/65">{command.endpoint ?? "Parser only"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      ))}
    </div>
  );
}