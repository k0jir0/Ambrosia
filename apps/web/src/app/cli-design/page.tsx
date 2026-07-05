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
    </div>
  );
}
