# Ambrosia Production Standard

This document turns Index119 into deployable controls. A release is not called
production-ready until the repository checks and the environment evidence below
are both complete.

## Trust boundaries

- Browsers, mobile clients, CLI clients, retrieved documents, model output, and
  provider responses are untrusted.
- The FastAPI production boundary authenticates managed bearer identities and
  enforces role levels on the server. `X-Ambrosia-Role` is accepted only outside
  staging and production.
- Agent output is advisory. Human approval and deterministic hot-path policy are
  separate authorities.
- PostgreSQL is authoritative in production. Process-local state is permitted
  only for development and degraded demonstrations.

## Required production configuration

| Variable | Requirement |
| --- | --- |
| `ENVIRONMENT` | `production` or `staging` |
| `DATABASE_URL` | Managed PostgreSQL connection with TLS |
| `REQUIRE_DATABASE` | `true` |
| `AMBROSIA_API_KEYS_JSON` | Managed secret containing scoped service identities |
| `AMBROSIA_JWT_HS256_SECRET` | Managed 32+ byte signing secret for interactive access tokens |
| `AMBROSIA_JWT_ISSUER` / `AMBROSIA_JWT_AUDIENCE` | Exact token scope expected by the API |
| `ALLOW_INSECURE_DEV_IDENTITY` | `false` |
| `ALLOWED_ORIGINS` or regex | Exact deployed clients only |
| `TRADINGVIEW_WEBHOOK_SECRET` | Managed random secret when webhooks are enabled |
| `HOTPATH_REQUIRE_APPROVAL` | `true` for an execution deployment |
| `HOTPATH_APPROVALS_JSON` | Short-lived approval digests delivered out of band |

Keys are rotated at least every 90 days and immediately after suspected
exposure. Logs, screenshots, support tickets, and release artifacts must not
contain secret values.

## Service objectives

- API availability: 99.9% measured monthly, excluding declared maintenance.
- API latency: 95% of non-background API requests below 500 ms.
- Deterministic pre-trade checks: 99% below 50 ms within the service boundary.
- Market-data freshness: clearly labeled and no older than the configured
  strategy maximum; stale data blocks execution readiness.
- Audit durability: every privileged write recorded; no acknowledged audit loss.
- Background jobs: 99% start within 60 seconds and finish within their declared
  timeout.
- Recovery point objective: 15 minutes. Recovery time objective: 60 minutes.

Targets must be adjusted from measured capacity before accepting real workload.

## Release evidence

Each release records the commit, environment, schema version, configuration
fingerprints (never values), test results, load-test results, migration result,
backup status, approver, start/end time, and rollback decision. `/ready` must be
green before traffic is shifted. `/live` is process liveness only.

## Backup and recovery

Managed PostgreSQL backups are encrypted and retained according to organizational
policy. At least quarterly, restore a backup into an isolated environment,
validate schema and row counts, run API smoke tests, record elapsed time, and
destroy the restored data under the retention policy. A backup that has not been
restored successfully is not considered verified.

## Incident ownership

The deployment owner assigns an on-call service owner, security contact, database
owner, and investment-control owner. Alert routes are tested quarterly. See
`INCIDENT_RUNBOOK.md` for response procedures.

## Known external gates

Repository code cannot assign personnel, provision managed identity and secret
systems, accept regulatory obligations, perform an independent penetration test,
or accumulate uptime history. Those gates require named organizational owners
and deployed-environment evidence.
