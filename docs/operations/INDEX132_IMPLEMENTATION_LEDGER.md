# Index132 implementation ledger

This is the handoff ledger for the implementation roadmap in
`papers-main/index132.txt`. It distinguishes repository-complete work from
external release evidence. The release decision remains **NO_GO** until every
external gate is passed with an evidence reference.

## Repository implementation

| Roadmap area | Implemented evidence | Repository status |
| --- | --- | --- |
| Reproducible baseline | Frozen Python/JavaScript dependencies, API/root/web/browser gates, migration verifier, generated route/OpenAPI contracts | Complete |
| Product scope | Public promise, auth/onboarding, private decision home, guided-or-own-thesis entry, focused production navigation, honest company-proof page | Complete |
| Identity | Database repositories, Argon2id, verification, login, reset, CSRF, bounded sessions, revocation, invitations, team suspension/reactivation, audit events | Complete |
| Tenancy | Server-derived principal, request/thread tenant context, V0008 organization schema, PostgreSQL RLS, quarantine organization, adversarial isolation tests | Complete; live RDS evidence external |
| Durable outputs | Tenant-bound object keys, content hashes, artifact catalogue, S3/KMS persistence, presigned downloads, readiness dependency | Complete; live AWS evidence external |
| Adoption measurement | Fixed minimized taxonomy, idempotent writes, organization activation report, admin UI, explicit non-traction disclaimer | Complete; observed usability/retention external |
| Local Ollama | Revocable outbound worker, loopback Ollama, strict JSON schema, job leases, run catalogue, human review, frozen six-case protocol | Complete; model execution/promotion evidence external |
| AWS target | Terraform for networking, CloudFront/WAF/ALB, ECS, RDS, Redis, S3/KMS, SES, secrets, observability, scaling, and migrations | Complete; apply/cutover external |
| Supply chain | Multi-stage containers, scan-before-push, SBOMs, immutable action pins, keyless signing, digest deployment | Complete; successful protected workflow run external |
| Migration | Render inventory template, ordered migrations, read-only source/target validator, two-rehearsal and rollback runbook | Complete; operator rehearsals external |
| Claims/governance | Claims register, threat model, production standard, legal/privacy pages, evidence template, fail-closed readiness decision | Complete; counsel/security/customer evidence external |

## Verification snapshot — 2026-08-07

- FastAPI suite: 234 passed, 3 skipped PostgreSQL integration tests.
- Root unit suite: 85 passed.
- Browser suite: 50 passed across desktop Chromium and tablet.
- Web: ESLint passed, TypeScript passed, optimized 33-route build passed.
- Mobile: TypeScript passed; 10 Jest tests passed.
- CLI/deployment contracts: 22 passed; 6 environment-gated tests skipped.
- Focused governed-artifact boundary: 4 passed.
- Ruff on every Index132-owned Python file: passed.
- Terraform 1.15.8 with locked AWS/random providers: format and validate passed.
- Database migration chain: V0001 through V0008 passed static verification.
- Route/OpenAPI exposure: 89 routes and five filtered documents generated and verified.
- Ollama protocol: six frozen cases validated; no model-performance run was asserted.
- Index119 repository readiness: passed.
- Index132 readiness: `NO_GO`, with external gates pending as designed.

The three skipped API tests require a disposable PostgreSQL runtime role and
exercise real RLS. They are enabled by `RUNTIME_DATABASE_URL`; absence of a
local PostgreSQL server is not converted into a pass.

## External closure gates

The authoritative list is
`docs/operations/index132-external-evidence.template.json`. At handoff it
contains sixteen pending gates:

1. AWS account baseline approval.
2. Verified Render inventory.
3. AWS staging deployment.
4. Two successful migration rehearsals.
5. Backup restore and rollback rehearsals.
6. Load/fault evidence and independent security review.
7. SES production sending.
8. Guided usability observation and counsel review.
9. Ollama release evaluation against the preregistered suite.
10. Production cutover and 72-hour bake.
11. Repeated paid-design-partner evidence.

These gates need credentials, independent reviewers, target users, elapsed
observation time, or real commercial events. Code cannot honestly manufacture
them. Use `scripts/generate-index132-readiness.py --require-release-ready` in
the protected release environment; it must return nonzero until they close.

## Operator next action

Create an access-controlled copy of the external evidence template, name the
release commander/database operator/security reviewer/product owner, complete
the Render dashboard inventory, and bootstrap AWS staging according to
`AWS_MIGRATION_RUNBOOK.md`. Do not move production traffic during the first
infrastructure apply.
