# Ambrosia

Ambrosia is an investment-decision workspace built to help investors
**pressure-test investment theses against evidence, expose weaknesses, and
document the reasoning behind their decisions.** Models are advisory; people
retain decision authority. Ambrosia is not an autonomous trading system.

## Project status

Documentation reviewed on **September 29, 2026**.

- **Source branches:** this guide describes the
  [`stagingfix` source tree](https://github.com/k0jir0/Ambrosia/tree/stagingfix).
  The repository home page on `main` carries this overview, but its application
  code is older. AWS deployment uses the separately approved `staging` branch;
  updating this README does not merge or deploy application code.
- **Hosting:** AWS is the current deployment platform. Ambrosia no longer
  deploys on Render. Remaining Render configuration, URLs, and migration notes
  in older files are legacy material, not current deployment instructions.
- **Environment:** the configured release workflow targets AWS **staging**.
  The recorded staging entry point is
  <https://d1c00nr674401f.cloudfront.net/>. This README is not a live uptime or
  production-readiness attestation.
- **Release authority:** use the current workflow, runtime configuration, and
  approved evidence. Historical "100% complete" documents and passing health
  checks do not establish model quality, security certification, or investment
  performance.

## License

Ambrosia is distributed under the MIT License. See [LICENSE](https://github.com/k0jir0/Ambrosia/blob/stagingfix/LICENSE) for the
full text.

## Core workflow

1. Create an account and organization workspace, then complete verification.
2. Enter an instrument, investment thesis, horizon, expression, and source pointers,
  or open a dated illustrative sample.
3. Create a review draft and decision packet. Initial review creation is not the
  same as completed evidence retrieval or model analysis.
4. Refresh available market context, run configured specialist analysis, and
  inspect evidence, disagreement, missing information, and policy gates.
5. Review the advisory output and record a human decision.
6. Attach an observed outcome and retain the decision history for later review.

The principal web experience focuses on this decision loop. Scanner, ticker
research, and experimental labs depend on feature flags and the deployed
configuration; not every repository module is exposed in staging.

## Implemented repository scope

- Next.js public, authentication, onboarding, decision, team, company-proof,
  privacy, terms, and administration surfaces.
- Database-backed signup, Argon2id password hashing, email verification, login,
  reset, invitations, session rotation/revocation, CSRF protection, and audit
  events.
- Server-derived organization context and PostgreSQL row-level security for
  tenant-owned product, analytics, model, and artifact records.
- Adversarial review, packet, provenance, deterministic risk, outcome, report,
  signal, and decision-memory workflows.
- Privacy-minimized activation telemetry with a fixed taxonomy and idempotency.
- KMS-encrypted S3 artifact persistence for AWS deployments, content hashes, a durable
  database catalogue, and short-lived tenant-scoped download URLs.
- An outbound-only local Ollama worker protocol with revocable credentials,
  strict structured output, model/prompt/evidence metadata, human review, and a
  frozen evaluation suite. Ollama output is advisory.
- AWS Terraform for CloudFront, WAF, ALB, private ECS/Fargate services, RDS
  PostgreSQL, TLS Redis, S3/KMS, SES/DKIM/SPF/DMARC, Secrets Manager,
  autoscaling, logs, alarms, and protected migration tasks.
- An AWS release workflow configured to build once, scan before push, emit SBOMs,
  sign image digests, deploy immutable digests, and separate migration from
  runtime credentials.

## Architecture

```text
Browser -> CloudFront/WAF -> /api/* -> ALB -> private FastAPI ECS tasks
                         -> /*      -> ALB -> private Next.js ECS tasks
FastAPI -> RDS PostgreSQL (tenant RLS)
        -> TLS Redis (distributed rate limits/coordination)
        -> S3 + KMS (governed artifacts)
        -> SES (verification, recovery, invitations)
Local worker -> outbound TLS -> Ambrosia job API -> loopback Ollama
```

The deterministic Rust hot-path boundary remains separate from advisory model
processing. No LLM belongs in a live order-validity or kill-switch loop.

## Repository layout

- `apps/web/` — Next.js product
- `services/api/` — FastAPI service and tests
- `services/hotpath-rs/` — deterministic Rust safety boundary
- `packages/local-worker/` — outbound local Ollama worker
- `packages/evals/` — model and workflow evaluation protocols
- `packages/cli/`, `packages/sdk-python/` — operator interfaces
- `infra/aws/` — AWS infrastructure as code
- `infra/db/` — schema and ordered migrations
- `scripts/` — migration, validation, evidence, and local-stack automation
- `docs/operations/` — current operational and release authority
- `docs/session-archives/` — historical planning material, not current proof

Older percent-complete documents and historical deployment notes are not
release evidence. Current claims are governed by
[the release claims register](https://github.com/k0jir0/Ambrosia/blob/stagingfix/docs/operations/RELEASE_CLAIMS_REGISTER.md) and
[the implementation ledger](https://github.com/k0jir0/Ambrosia/blob/stagingfix/docs/operations/INDEX132_IMPLEMENTATION_LEDGER.md),
read alongside the current code and release evidence.

## Local development

Requirements: Node.js 20+, pnpm 9.12.0, Python 3.12+, and
[uv](https://docs.astral.sh/uv/). AWS validation additionally requires Docker,
Terraform, and appropriately scoped AWS credentials.

### Windows quick start

For a fresh checkout of the source described here:

```powershell
git clone --branch stagingfix https://github.com/k0jir0/Ambrosia.git
cd Ambrosia
```

From that repository root:

```powershell
pnpm install --frozen-lockfile
uv sync --project services/api --frozen
pnpm local:serve
```

Default local addresses:

- Web: <http://127.0.0.1:3000>
- API: <http://127.0.0.1:8000>
- API documentation: <http://127.0.0.1:8000/docs>

The `local:*` commands use PowerShell scripts. To run the web and API separately,
use separate terminals:

```powershell
pnpm local:web:serve
pnpm local:api:serve
```

Background lifecycle commands are `pnpm local:start`, `pnpm local:status`,
`pnpm local:logs`, and `pnpm local:stop`.

### Direct development commands

For environments without the Windows launch scripts, start the web from the
repository root with `pnpm dev:web`. In another terminal:

```sh
cd services/api
uv run --frozen uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Local development can use in-memory adapters and fallback data. Configure real
providers and persistence explicitly when testing integrations. Browser-local
drafts, fixture data, and successful page rendering do not prove a canonical
server save or completed analysis. Do not use production credentials for local
experiments or commit secrets.

### Local model worker

The outbound Ollama worker is a separate process from the web/API stack. Running
the web app does not start a model or enroll a worker. The governed review path
requires a tenant-enrolled, compatible worker and an approved model digest; see
[the worker implementation](https://github.com/k0jir0/Ambrosia/blob/stagingfix/packages/local-worker/ambrosia_local_worker.py) and
[the operation bridge](https://github.com/k0jir0/Ambrosia/blob/stagingfix/services/api/app/ollama_bridge.py). Model output remains
advisory and must follow the configured proposal/admission workflow.

## Verification

Run applicable checks from the repository root:

```powershell
pnpm lint:web
pnpm build:web
pnpm test:e2e
pnpm lint:api
pnpm test:api
pnpm test:unit
python scripts/verify-migrations.py
python scripts/verify-index119-readiness.py
python scripts/verify-aws-staging-control-plane.py
```

The focused review tests can be run independently:

```powershell
uv run --project services/api --frozen pytest tests/unit-tests/test_backend_review_engine_unit.py tests/unit-tests/test_index157_pipeline_unit.py --confcutdir=tests/unit-tests -q -p no:cacheprovider
```

These tests cover selected contracts and mocked/model-independent behavior, not
live model quality or a deployed end-to-end journey. On Windows, use an explicit
writable `--basetemp` if pytest's default temporary directory is inaccessible.

Terraform validation:

```powershell
terraform -chdir=infra/aws fmt -check -recursive
terraform -chdir=infra/aws init -backend=false
terraform -chdir=infra/aws validate
```

PostgreSQL integration tests require `RUNTIME_DATABASE_URL`. Supply test database
credentials through your environment; do not include them in logs or evidence.

The [Ollama evaluation script](https://github.com/k0jir0/Ambrosia/blob/stagingfix/packages/evals/run_ollama_disconfirmation_eval.py)
without model outputs only validates a frozen protocol and reports
`not_executed`. It is not a model-quality benchmark result. Its current threshold
logic also needs correction before it can serve as a quality gate.

## AWS deployment

The deployment entry point is the
[AWS release workflow](https://github.com/k0jir0/Ambrosia/blob/staging/.github/workflows/aws-release.yml), backed by
[Terraform in infra/aws](https://github.com/k0jir0/Ambrosia/tree/staging/infra/aws). **Do not use Render deploy buttons,
Render service URLs, or `render.yaml` to deploy the current application.**

The configured apply path requires:

1. The protected `staging` branch and GitHub `staging` environment approvals.
2. A full `candidate_sha` matching the selected workflow commit.
3. AWS OIDC deployment access, protected remote Terraform state, and the required
  repository/environment variables and secrets listed in the workflow.
4. Container validation, image scanning, database migration, deployment, and
  environment-specific validation under that workflow.

Use GitHub Actions to dispatch **AWS release** on `staging`, select the staging
environment, supply the approved commit SHA, and enable `apply` only for an
authorized deployment. A README push to `main` does not invoke this protected
AWS apply path. The current workflow does not expose a production deployment
option; do not describe a staging release as a production cutover.

Review release evidence separately from infrastructure deployment. The staging
and broader readiness commands are:

```powershell
python scripts/generate-index133-staging-readiness.py `
  --external-evidence <approved-staging-evidence.json> `
  --require-live

python scripts/generate-index132-readiness.py `
  --external-evidence <approved-evidence.json> `
  --require-release-ready
```

Use the [staging evidence template](https://github.com/k0jir0/Ambrosia/blob/stagingfix/docs/operations/index133-staging-evidence.template.json)
and [broader release template](https://github.com/k0jir0/Ambrosia/blob/stagingfix/docs/operations/index132-external-evidence.template.json).
The strict commands must fail until their required gates have approved evidence.
Neither a successful deploy nor a readiness artifact alone certifies research
quality, recovery readiness, or public-beta suitability.

### Legacy documentation

The [AWS migration runbook](https://github.com/k0jir0/Ambrosia/blob/stagingfix/docs/operations/AWS_MIGRATION_RUNBOOK.md) contains
historical migration and rehearsal procedures. Older deployment guides, Render
configuration, and migration-only environment variables may remain in the
repository for reference. They are not prerequisites for normal AWS releases or
local development. Use the current workflow for deployment requirements rather
than following an archived "deploy now" or percent-complete report.

## Known limitations

The September 2026 source audit identified gaps between a completed workflow
object and validated analysis:

- **Initial reviews are drafts:** [the generator](https://github.com/k0jir0/Ambrosia/blob/stagingfix/services/api/app/review_engine.py)
  uses template critiques and tests, a pending historical analogue, and a fixed
  initial confidence value. Creating a review does not retrieve its source URLs.
- **Verification is incomplete:** claim-verification coverage and missing-source
  disconfirmation checks need correction before their pass labels can be treated
  as substantive evidence validation.
- **Fallbacks are not research:** generated market data can lose its explicit
  synthetic label during evidence construction. Browser fallbacks can preserve
  a local review after API failure. Inspect origin and persistence state.
- **Quantitative outputs need qualification:** the controlled backtest in
  [day6.py](https://github.com/k0jir0/Ambrosia/blob/stagingfix/services/api/app/day6.py) generates seeded synthetic metrics, not a
  historical strategy simulation. Position-size units and heuristic risk and
  confidence calculations need correction or clearer boundaries.
- **Quality gates are not yet sufficient:** the unsupported-claim threshold in
  the Ollama evaluator has an inverted comparison. Passing schema or fixture
  tests does not establish model accuracy or investment usefulness.
- **Client and feature parity remains work:** mobile decision writeback and
  experimental modules should not be assumed equivalent to the governed web
  workflow. Feature flags and worker configuration affect what is available.

The next reliability milestone is a narrow end-to-end review using authentic,
inspectable evidence, complete claim verification, honest abstention, consistent
units, and a durable human decision. These limitations are documented here, not
claimed to have been fixed by this README update.

## Claims boundary

Do not claim returns, alpha, enterprise-grade security, compliance, model
improvement, AWS production hosting, paid customers, retention, or revenue
without the scoped evidence and approvals named in the release claims register.
Guided data is a dated illustrative sample, not live market data or a customer
result.
