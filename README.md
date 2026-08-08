# Ambrosia

Ambrosia is a governed investment-decision workspace. It helps an investment
team challenge a thesis, preserve evidence and disagreement, apply deterministic
risk gates, record a human decision, and learn from the outcome. Models advise;
they never hold decision authority or mutate a live brokerage account.

## The first product journey

1. A visitor understands the product promise on the public landing page.
2. The user creates an email/password account and private organization.
3. Email verification opens a tenant-bound workspace and dated guided sample.
4. The user chooses the guided case or enters a thesis.
5. Ambrosia builds an adversarial decision packet with provenance, uncertainty,
   strongest disagreement, missing evidence, and risk/policy gates.
6. The user records the decision and can later attach the observed outcome.
7. Organization administrators can inspect minimized activation evidence,
   sessions, team members, governed artifacts, and catalogued local-model runs.

The signed-in production navigation intentionally exposes only the sellable
decision loop. Research labs remain available in development or behind
`NEXT_PUBLIC_ENABLE_LABS=true`.

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
- KMS-encrypted S3 artifact persistence in production, content hashes, a durable
  database catalogue, and short-lived tenant-scoped download URLs.
- An outbound-only local Ollama worker protocol with revocable credentials,
  strict structured output, model/prompt/evidence metadata, human review, and a
  frozen evaluation suite. Ollama output is advisory.
- AWS Terraform for CloudFront, WAF, ALB, private ECS/Fargate services, RDS
  PostgreSQL, TLS Redis, S3/KMS, SES/DKIM/SPF/DMARC, Secrets Manager,
  autoscaling, logs, alarms, and protected migration tasks.
- An AWS release workflow that builds once, scans before push, emits SBOMs,
  signs image digests, deploys immutable digests, and separates migration from
  runtime credentials.
- Render-to-AWS inventory, rehearsal, validation, cutover, rollback, and
  evidence procedures.

Infrastructure code is not evidence that AWS is deployed. Repository code is
not evidence of model quality, legal approval, security certification, customer
traction, or investment performance. The machine-readable readiness result
stays `NO_GO` until the external gates have approved evidence.

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
`docs/operations/RELEASE_CLAIMS_REGISTER.md` and
`docs/operations/INDEX132_IMPLEMENTATION_LEDGER.md`.

## Local development

Requirements: Node.js 20+, pnpm 9.12, Python 3.12, and uv.

```powershell
pnpm install --frozen-lockfile
pnpm local:serve
```

The web and API can also be started independently:

```powershell
pnpm local:web:serve
pnpm local:api:serve
```

Development may use an in-memory identity/persistence adapter and deterministic
fallback data. Staging and production fail closed when PostgreSQL, Redis,
artifact storage, or required secrets are unavailable.

## Verification

Primary repository gates:

```powershell
pnpm lint:web
pnpm build:web
pnpm test:e2e
pnpm lint:api
pnpm test:api
pnpm test:unit
python scripts/verify-migrations.py
python scripts/verify-index119-readiness.py
python packages/evals/run_ollama_disconfirmation_eval.py
python scripts/generate-index132-readiness.py
```

Terraform validation:

```powershell
terraform -chdir=infra/aws fmt -check -recursive
terraform -chdir=infra/aws init -backend=false
terraform -chdir=infra/aws validate
```

PostgreSQL integration tests require `RUNTIME_DATABASE_URL`. Migration
comparison requires read-only `RENDER_DATABASE_URL` and `AWS_DATABASE_URL`.
No credential values belong in logs or evidence JSON.

## AWS migration and release

Follow `docs/operations/AWS_MIGRATION_RUNBOOK.md`. The sequence is inventory,
AWS staging, two isolated data rehearsals, restore and rollback rehearsals,
approved production cutover, and a minimum 72-hour bake. Render remains a
deploy-frozen recovery target until the bake and formal go decision complete.

The current external-evidence template is
`docs/operations/index132-external-evidence.template.json`. Run:

```powershell
python scripts/generate-index132-readiness.py `
  --external-evidence <approved-evidence.json> `
  --require-release-ready
```

The command must fail until every external gate is passed and linked to real
evidence. That failure is a safety property, not missing repository work.

## Claims boundary

Do not claim returns, alpha, enterprise-grade security, compliance, model
improvement, AWS production hosting, paid customers, retention, or revenue
without the scoped evidence and approvals named in the release claims register.
Guided data is a dated illustrative sample, not live market data or a customer
result.
