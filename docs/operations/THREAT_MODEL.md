# Ambrosia Threat Model

Protected assets include identities, provider and market-data credentials,
portfolio context, theses, evidence, approvals, signals, policies, audit records,
and execution proposals.

Principal threats and controls:

| Threat | Primary controls |
| --- | --- |
| Forged role header | Production bearer identity validation and server policy |
| Credential disclosure | Managed secrets, redacted logs, rotation and revocation |
| Prompt/retrieval injection | Untrusted-input handling, tool allowlists, human review |
| Approval substitution | Order-specific digest, policy version, expiry and nonce |
| Request/order replay | API idempotency records and hot-path replay guard |
| Policy bypass | Admin-only writes, audit events, deterministic enforcement |
| Stale or fallback data | Provenance/freshness labels and domain alerts |
| Denial of service | Body limits, rate limits, bounded retries and circuit breakers |
| Audit tampering | Hash-chained events and restricted audit access |
| Single-instance state loss | Required PostgreSQL and durable leased-job schema |
| Dependency compromise | Locked dependencies, scanning and controlled releases |

Residual risks include compromised administrator endpoints, malicious insiders,
provider misinformation, model-quality degradation, and failures in external
cloud controls. They require independent review, least privilege, monitoring,
and organizational response procedures in addition to repository code.
