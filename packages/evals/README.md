# Evaluation Harness

The first eval suite should run before private beta and eventually in CI.

Eval categories:

- Disconfirming-test quality
- Invalid validation/refusal behavior
- Prompt-injection resistance
- Tradeability missing-data surfacing
- Baseline comparison against a strong general AI answer
- Structured schema validity

The JSONL fixtures here are intentionally small and human-readable.

## Provider Ablation Matrix

Run a cost/latency/quality tradeoff comparison across provider modes:

```powershell
pnpm evals:ablation
```

By default this generates:

- `artifacts/provider-ablation.json`
- `artifacts/provider-ablation.md`

CI uploads these artifacts on every run as the `provider-ablation-report` evidence bundle.