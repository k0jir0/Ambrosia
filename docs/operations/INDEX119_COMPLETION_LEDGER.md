# Index119 Completion Ledger

Prepared July 21, 2026. This ledger distinguishes implemented controls from
evidence that can only be produced in a deployed environment.

## Implemented and locally verified

- Production fails closed without a configured bearer API identity or an
  expiring HS256 identity token.
- JWT signature, expiration, not-before, issuer, audience, subject, team, and
  role claims are validated without trusting client role headers.
- Server-side route policy, request-size limits, rate limits, security headers,
  correlation IDs, structured security events, and audit access restrictions
  are active.
- Security audit events are hash chained in-process and use a globally ordered,
  advisory-lock-protected PostgreSQL chain when the database is configured.
  Audit persistence failure makes readiness fail and blocks later production
  writes.
- Jobs support idempotent creation, atomic PostgreSQL claim, leases, attempts,
  timeouts, cancellation, completion, and expired-lease requeueing.
- Provider calls have bounded retries, jitter, timeouts, circuit breakers, and
  visible failure telemetry.
- Liveness and readiness are separate. Production readiness verifies identity,
  required persistence, and durable audit health.
- Prometheus-compatible operational/domain telemetry, alert rules, synthetic
  monitoring, capacity probing, threat modeling, service objectives, release
  rules, and incident/recovery runbooks exist.
- Next.js and API security headers are configured. Render uses `/ready`, required
  PostgreSQL, disabled development identity, and managed secret placeholders.
- The deterministic Rust boundary validates fields, notional, price collar,
  model origin, kill switch, approval binding, policy version, expiry, and nonce
  replay.
- Database migration v0006 supplies durable jobs, security audits, and execution
  replay guards.
- CI runs CodeQL, dependency audits, Index119 evidence checks, PostgreSQL
  integration tests, and Rust hot-path tests.

## Local evidence

- FastAPI with PostgreSQL enabled: 212 passed, including durable job and global
  audit-chain integration tests.
- Repository unit tests: 85 passed.
- Index119 API/security tests: 10 passed.
- Web lint and optimized production build: passed.
- Ruff, Python compilation, migration/version checks, Rust formatting, and
  repository readiness checks: passed.
- Capacity probe: 200 requests, concurrency 20, zero errors, 63.94 ms p95 on the
  local development machine. This is development evidence, not a production
  capacity guarantee.
- Linux-container Rust validation: 4 passed, including deterministic guardrails,
  approval mismatch, and nonce replay rejection.
- PostgreSQL recovery drill: a custom-format backup was restored into an
  isolated database and the durable_job, security_audit_event, and
  execution_replay_guard tables were verified before cleanup.
- GitHub PR #1 was created, but hosted Actions jobs were prevented from starting
  by the account billing/spending-limit state. Local Docker verification covers
  the PostgreSQL and Linux Rust jobs until hosted runners are re-enabled.

## External acceptance gates

These cannot be truthfully marked complete by source-code changes:

1. Provision the managed PostgreSQL, secrets, identity issuer, monitoring store,
   alert destinations, TLS/domain, and backup service in the target account.
2. Apply migration v0006 to the managed staging/production database; local
   PostgreSQL integration and restore drills already pass.
3. Re-run the PostgreSQL and Rust hosted CI jobs after GitHub Actions billing is
   restored; equivalent local Linux-container checks already pass.
4. Assign named service, security, database, investment-control, and incident
   owners.
5. Conduct an independent penetration test and resolve accepted findings.
6. Execute and record a backup restoration and failover exercise against the
   target managed database.
7. Run staging load/stress tests against approved traffic targets.
8. Exercise alert delivery, kill-switch response, rollback, and incident
   communications with the assigned owners.
9. Collect the required uptime, latency, recovery, audit-durability, data-
   freshness, and job-completion evidence over the agreed observation period.
10. Obtain legal, regulatory, privacy, and financial-control acceptance for the
    intended jurisdiction and use.

The repository is ready to enter those acceptance gates. It is not honest to
label the deployed service professionally certified until every applicable gate
has named evidence and approval.
