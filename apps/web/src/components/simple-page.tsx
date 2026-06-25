import { Panel, SectionTitle } from "./ui";

export function SimplePage({ title, description }: { title: string; description: string }) {
  return (
    <div className="space-y-4">
      <Panel className="p-6">
        <SectionTitle eyebrow="Ambrosia" title={title} />
        <p className="mt-3 max-w-3xl text-sm text-ink/75">{description}</p>
      </Panel>
      <Panel className="p-6 text-sm text-ink/70">
        This route is now part of the multi-page architecture and ready for deeper feature implementation.
      </Panel>
    </div>
  );
}
