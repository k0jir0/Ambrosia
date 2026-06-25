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

## Retrieval Benchmark + Drift Gate

Run the retrieval benchmark against fixture scenarios and compare against the
tracked baseline:

```powershell
pnpm evals:retrieval
```

To refresh the baseline when retrieval behavior intentionally changes:

```powershell
cd services/api
uv run python ../../packages/evals/run_retrieval_benchmark.py --update-baseline
```

Tracked inputs and baseline:

- `packages/evals/retrieval_fixtures.json`
- `packages/evals/retrieval_baseline.json`

Generated report artifacts:

- `artifacts/retrieval-benchmark.json`
- `artifacts/retrieval-benchmark.md`