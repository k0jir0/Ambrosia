# Ambrosia Incident Runbook

## First response

1. Acknowledge the alert and open an incident record with UTC timestamps.
2. Determine whether confidentiality, decision integrity, execution controls,
   audit durability, or availability is affected.
3. If execution safety is uncertain, enable the deterministic kill switch and
   prevent new execution-readiness promotions.
4. Preserve logs, traces, request IDs, deployment identifiers, and audit-chain
   evidence. Never paste secrets into the incident record.
5. Assign incident commander, technical lead, communications lead, and financial
   control owner.

## Critical conditions

- Kill switch unavailable or bypass suspected: stop execution ingress, revoke
  execution credentials, and verify the last accepted order independently.
- Unauthorized access or secret exposure: revoke affected credentials, preserve
  access logs, rotate dependent credentials, and scope accessed data.
- Stale or false market data: mark provider unhealthy, block execution readiness,
  display fallback provenance, and identify affected decisions.
- Audit write failure or chain mismatch: block privileged writes, preserve the
  database and application logs, and reconcile by request ID.
- Database loss or corruption: stop writes, invoke managed recovery, and validate
  restored schema, row counts, audit continuity, and application smoke tests.

## Recovery and closure

Restore only after the failed control has been tested. Monitor the repaired path,
record the timeline and affected decisions, notify required stakeholders, and
create corrective actions with owners and dates. Rotate any credentials exposed
during diagnosis. Conduct a blameless review and update alerts, tests, and this
runbook.
