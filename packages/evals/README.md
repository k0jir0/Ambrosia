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

## Ollama disconfirmation treatments

Validate the frozen protocol without making a model-quality claim:

```powershell
pnpm evals:ollama-disconfirmation
```

Evaluate a completed, blinded three-treatment run and enforce the release gates:

```powershell
python packages/evals/run_ollama_disconfirmation_eval.py `
  --outputs artifacts/ollama-treatment-outputs.json `
  --require-treatments `
  --require-release-thresholds
```

Each case must have `deterministic`, `auto_admit`, and `human_admit` records.
The harness reports aggregate and per-treatment schema validity, evidence-reference
precision, abstention behavior, unsupported material claims, security violations,
and human usefulness. A protocol-only run is explicitly labelled `not_executed`;
it is not evidence that Ollama improves report quality.

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

## Scanner Benchmark + Drift Gate

Run scanner discovery benchmark against fixture scenarios:

```powershell
pnpm evals:scanner
```

To refresh scanner baseline when scanner behavior intentionally changes:

```powershell
cd services/api
uv run python ../../packages/evals/run_scanner_benchmark.py --update-baseline
```

Tracked scanner inputs and baseline:

- `packages/evals/scanner_fixtures.json`
- `packages/evals/scanner_baseline.json`

Generated scanner artifacts:

- `artifacts/scanner-benchmark.json`
- `artifacts/scanner-benchmark.md`
