# Ambrosia

Ambrosia is a governed investment-decision workspace. It helps an investment
team challenge a thesis, preserve evidence and disagreement, apply deterministic
risk gates, record a human decision, and learn from the outcome. Models advise;
they never hold decision authority or mutate a live brokerage account.

## License

Ambrosia is distributed under the MIT License. See [LICENSE](LICENSE) for the
full text.

## Current staging state

AWS staging is deployed from the protected `staging` branch at:

<https://d1c00nr674401f.cloudfront.net/>

The most recent applied AWS release before this README update was successful
for staging commit `97f040d16be3a2c791750988c7592a707787a38b` in workflow run
`31269029604`. On August 8, 2026, the landing, login, signup, onboarding,
`/api/live`, and `/api/ready` routes returned HTTP 200. Readiness reported
healthy persistence, artifact storage, distributed rate limiting, account
identity, and identity checks. The environment uses synthetic data, generated
CloudFront addressing, one API task, and one web task in `ca-central-1`; no
website custom domain is enabled.

Transactional email is qualified but not activated. The SES domain identity
`agentresearchcompany.com` is verified in AWS account `111204669733` and
`ca-central-1`; Easy DKIM RSA 2048 and signing report `SUCCESS`, DMARC monitoring
is published with `p=none`, and a mailbox-simulator send succeeded through the
`ambrosia-staging-transactional` configuration set. SES uses its default MAIL
FROM domain so the existing Namecheap email-forwarding MX and SPF records
remain intact. Account-level suppression covers bounces and complaints, and
the enabled event destination publishes bounce, complaint, and reject events.

AWS production access remains disabled while Support reviews case
`178621567500544`. The SES API review status remains `DENIED`, while the console
shows `More information needed` and contains the verified-domain response sent
on August 8, 2026. `AUTH_EMAIL_FROM` and `AUTH_SES_IDENTITY_ARN` remain unset in
the staging environment, so verification and password recovery continue to
fail closed rather than claim deliverability. Do not set those variables until
`ProductionAccessEnabled=true`; keep `CUSTOM_DOMAIN_ENABLED=false` because DNS
remains authoritative in Namecheap rather than Route53.

This proves that the current staging web and API are deployed and reachable. It
also proves SES domain ownership, DKIM qualification, and sandbox submission.
It does not prove SES production access, inbox placement, production readiness,
unrestricted public-beta readiness, model quality, security certification,
backup recovery, or the complete signup-to-decision journey. The evidence-backed
Index133 readiness generator still returns `NO_GO` with 25 pending external
gates.

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

The AWS staging deployment is evidence of a reachable environment, but
repository code and basic health checks are not evidence of model quality,
legal approval, security certification, customer traction, investment
performance, or recovery readiness. The machine-readable release decision
stays `NO_GO` until the remaining external gates have approved evidence.

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
- `infra/db/` — schema and ordered migrations through `v0009`
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
python scripts/verify-aws-staging-control-plane.py
python packages/evals/run_ollama_disconfirmation_eval.py
python scripts/generate-index132-readiness.py
python scripts/generate-index133-staging-readiness.py
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

Follow `docs/operations/AWS_MIGRATION_RUNBOOK.md`. AWS staging is live on its
generated CloudFront hostname. The remaining sequence is evidence completion,
two isolated data rehearsals, restore and rollback rehearsals, an approved
production cutover, and a minimum 72-hour bake. Render remains a recovery
reference until the formal go decision supersedes it.

The current AWS staging evidence template is
`docs/operations/index133-staging-evidence.template.json`. Run:

```powershell
python scripts/generate-index133-staging-readiness.py `
  --external-evidence <approved-staging-evidence.json> `
  --require-live
```

For the broader release-readiness decision, use
`docs/operations/index132-external-evidence.template.json`:

```powershell
python scripts/generate-index132-readiness.py `
  --external-evidence <approved-evidence.json> `
  --require-release-ready
```

The command must fail until every external gate is passed and linked to real
evidence. That failure is a safety property, not missing repository work.

## Current limitations

- The default production navigation exposes the governed decision loop. Market
  Scanner uses `NEXT_PUBLIC_ENABLE_MARKET_SCANNER` with
  `MARKET_SCANNER_ENABLED`; ticker intelligence is independently controlled by
  `NEXT_PUBLIC_ENABLE_MARKET_INTELLIGENCE` with
  `MARKET_INTELLIGENCE_ENABLED`. Market Intelligence is fail-closed in staging
  and production until its evidence panels are qualified. AWS release builds
  enable scanner discovery and review intake while keeping scanner promotion
  and unrelated research or execution capabilities disabled.
- AWS staging enforces governed selective integration, while the mobile client
  still uses a legacy direct decision endpoint. Mobile parity requires an
  enforced-mode compatibility update and test.
- The current administration surface focuses on identity, workers, activation,
  and artifacts. Earlier provider-health, alert, certification, metric, and
  tool-boundary panels do not yet have an equivalent staging-native operator
  console.
- The local API suite passes 240 tests with three skipped when run with an
  explicit writable `--basetemp`; the default shared Windows pytest temp and
  cache directories can be inaccessible on this workstation.
- pnpm 9 warns that the `pnpm` field in `package.json` no longer applies the
  configured overrides and audit settings. Dependency policy should be moved to
  the supported pnpm configuration surface.
- Portfolio Intelligence is not part of staging. The former local portfolio
  branch, integration worktree, migrations, and development servers were
  removed rather than merged.

## Claims boundary

Do not claim returns, alpha, enterprise-grade security, compliance, model
improvement, AWS production hosting, paid customers, retention, or revenue
without the scoped evidence and approvals named in the release claims register.
Guided data is a dated illustrative sample, not live market data or a customer
result.
