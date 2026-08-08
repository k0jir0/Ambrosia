# Ambrosia Threat Model

Protected assets include identities, provider and market-data credentials,
portfolio context, theses, evidence, approvals, signals, policies, audit records,
and execution proposals.

## Scope and trust boundaries

The browser, email links, invited users, local workers, Ollama/model output,
retrieved evidence, market providers, GitHub runners, container registries, and
Render migration source are untrusted inputs. The API identity boundary derives
user, role, and organization from an opaque server session; client role/tenant
headers never grant authority. PostgreSQL RLS is the second tenant boundary.
Redis is a required distributed abuse-control dependency in staging/production.
S3 keys are constructed from request tenant context and opaque object-reference
hashes. The local Ollama worker initiates outbound TLS and may access only jobs
bound to its revocable tenant credential.

Principal threats and controls:

| Threat | Primary controls |
| --- | --- |
| Forged role header | Production bearer identity validation and server policy |
| Password stuffing/session theft | Argon2id, generic recovery responses, lockout, opaque hashed sessions, idle/absolute expiry, CSRF, secure host cookie, Redis throttling |
| Verification/reset/invite replay | Keyed token hashes, exact high-entropy lookup, expiry, row lock, single use, session revocation |
| Cross-tenant object/job/search access | Request tenant context, repository predicates, tenant cache/object prefixes, PostgreSQL RLS, adversarial tests |
| Credential disclosure | Managed secrets, redacted logs, rotation and revocation |
| Prompt/retrieval injection | Untrusted-input handling, tool allowlists, human review |
| Approval substitution | Order-specific digest, policy version, expiry and nonce |
| Request/order replay | API idempotency records and hot-path replay guard |
| Policy bypass | Admin-only writes, audit events, deterministic enforcement |
| Stale or fallback data | Provenance/freshness labels and domain alerts |
| Denial of service | Body limits, rate limits, bounded retries and circuit breakers |
| Model exfiltration or injection | Outbound-only worker, loopback Ollama, fixed JSON schema, evidence allowlist, no secrets in prompts, human review |
| Future-information leakage | Observation cutoff in jobs/runs and point-in-time evaluation fixtures |
| Audit tampering | Hash-chained events and restricted audit access |
| Single-instance state loss | Required PostgreSQL and durable leased-job schema |
| Dependency compromise | Locked dependencies, scanning and controlled releases |
| AWS release scanner/action compromise | Full-commit action pins, minimal workflow permissions, OIDC short-lived credentials, pre-push scanning, SBOM, digest signing/deployment |
| Migration split brain | Single writable primary, maintenance freeze, checksummed backup, two rehearsals, rollback rehearsal, explicit divergence procedure |
| Misleading investor/customer claim | Claims register, visible data-mode labels, evidence owner, counsel/finance gates |

## Abuse cases that must stay in automated tests

- Sign up tenant A and tenant B; guessed packet, review, retrieval, LLM job/run,
  analytics, and object references from the other tenant return no data or a
  denial and cannot mutate state.
- Omit tenant context on the runtime database role; tenant-owned queries select
  no rows and writes fail.
- Present `X-Ambrosia-Role`/tenant headers with a lower-privilege session; the
  server principal wins.
- Reuse verification, reset, invitation, local-worker, CSRF, or session tokens;
  reuse fails and relevant sessions/credentials can be revoked.
- Submit untrusted evidence that asks the model to ignore policy or trade;
  schema verification and the frozen evaluation reject decision authority.
- Make Redis or durable audit persistence unavailable in production; readiness
  fails and protected traffic/writes fail closed.

## Data minimization and retention

Activation events use a fixed event/property taxonomy, hash object references,
and do not accept email or thesis text. Raw model prompts/completions are not
stored by default. Logs exclude secrets and proprietary content. Retention,
tenant deletion, legal hold, data-subject handling, SES bounce/complaint policy,
and support-access procedure require approved organizational policy and counsel.

Residual risks include compromised administrator endpoints, malicious insiders,
provider misinformation, model-quality degradation, and failures in external
cloud controls. They require independent review, least privilege, monitoring,
and organizational response procedures in addition to repository code.

Review this model before each release and after an incident, trust-boundary
change, new provider/tool, identity change, or new category of customer data.
An independent penetration test and cloud configuration review remain external
release gates; this document is not a security certification.
