import { SimplePage } from "@/components/simple-page";
import { GovernanceSurface } from "@/components/governance-surface";
import { BrokerSandboxPanel, ExecutionLoopPanel } from "@/components/advanced-panels";

export default function AdvancedPage() {
  return (
    <div className="space-y-4">
      <GovernanceSurface mode="advanced" />
      <BrokerSandboxPanel />
      <ExecutionLoopPanel />
      <SimplePage
        title="Advanced"
        description="Power-user workflows, calibration instrumentation, operational controls, and paper-only execution tools that are intentionally separated from default user onboarding routes."
      />
    </div>
  );
}
