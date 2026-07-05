# Index85 Evidence Matrix

| Index85 workstream | Primary artifact(s) | Enforcement gate |
| --- | --- | --- |
| Release distribution and provenance | `artifacts/release-evidence.json`, `artifacts/release-checksums.sha256` | `pnpm release:readiness:check` |
| Benchmark expansion (FinanceBench/FinQA/TAT-QA) | `artifacts/financebench-relay-trace.json`, `artifacts/finqa-relay-trace.json`, `artifacts/tatqa-relay-trace.json` | `pnpm index85:benchmarks:check` |
| Open FinLLM routing map | `artifacts/open-finllm-routing-map.json` | `pnpm index85:benchmarks:check` |
| Enterprise identity and lifecycle controls | `artifacts/enterprise-execution-readiness.json` | `pnpm enterprise:execution:check` |
| Production rollout evidence | `artifacts/rollout-evidence-packet.json` | `pnpm production:evidence:check` |
| Documentation alignment | `packages/cli/README.md`, `packages/sdk-python/README.md`, this matrix | `pnpm docs:consistency:check` |
