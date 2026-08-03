# Selective Integration Implementation

Status: code-complete controlled-rollout baseline
Contract: `selective-integration.v1`
Database migration: `v0007`
Source roadmaps: `papers/index123x.txt` and `papers/index124x.txt`

## Outcome

The selective-integration prototype is now implemented as a governed packet lifecycle rather than a display-only action. The implementation preserves the existing Ambrosia packet and review surfaces while making provenance, disconfirmation, deterministic risk, human decision authority, durable memory, and tamper evidence explicit and testable.

## Enforced invariants

- New packet artifacts use one canonical backend model and a published `packet.v1` JSON Schema.
- Legacy `null` list fields are normalized without treating absent evaluation results as pass.
- Packet input changes increment `packetVersion` and invalidate downstream integration results.
- Provenance is derived from actual packet sources, market snapshots, technical calculations, and sentiment adapters. Fallback and demo data are not relabeled as live.
- Disconfirmation evaluates falsifiability, null hypotheses, evidence presence, contradictions, and source references. Initial confidence is not used as a pass criterion.
- Disconfirmation records deterministic numeric recomputations and evaluator identity alongside its versioned input hash.
- Missing mandatory risk data returns `insufficient_data`; high-risk and stale-market cases return `blocked`.
- The authoritative packet-decision endpoint refuses packets that are not promotable.
- Outcome resolution is allowed only after a governed human decision.
- Decision memory separates checkpoints from forward outcome resolutions and rejects future observations during retrieval.
- PostgreSQL writes the integrated packet, memory checkpoint, optional outcome row, and audit event in one transaction.
- Audit events are forward-hashed, ordered under an advisory lock, and anchored by a separately stored chain head so tail truncation is detectable.
- Governed audit actors come from the authenticated request principal rather than a client-supplied label, and chain-position conflicts fail closed without disabling PostgreSQL.
- The workbench records decisions through the governed packet endpoint and shows workflow state, blockers, provenance mode, coverage, and staleness.
- Selective-stage, policy-block, write-conflict, and audit-verification counters are exposed through existing operational telemetry.

## API surfaces

- `POST /packets/{packet_id}/selective-integrate`
- `POST /packets/{packet_id}/provenance/refresh`
- `POST /packets/{packet_id}/disconfirmation/run`
- `POST /packets/{packet_id}/risk-gate/run`
- `GET /packets/{packet_id}/integration/status`
- `POST /packets/{packet_id}/decision`
- `GET /packets/{packet_id}/memory`
- `POST /packets/{packet_id}/memory/resolve`
- `GET /packets/{packet_id}/audit-chain/verify`
- `GET /packets/{packet_id}/versions`

The combined `selective-integrate` route is idempotent for an unchanged packet version. The staged routes are available for explicit orchestration and UI recovery flows.

## Data model

Migration `V0007__selective_integration_hardening.sql` adds:

- `packet_version`: immutable input-version snapshots;
- `decision_memory_record`: checkpoint and resolution records with hash linkage;
- `packet_audit_chain`: append-only ordered lifecycle events;
- `packet_audit_head`: independent last-sequence and last-hash anchor.

The existing `review_packet`, `decision_audit`, `metric_snapshot`, `retrieval_event`, and `outcome_record` tables remain in use.

## Rollout flags

```text
SELECTIVE_INTEGRATION_ENABLED=true
SELECTIVE_INTEGRATION_ENFORCED=false
```

Recommended rollout:

1. Apply migration `v0007` in staging.
2. Run with integration enabled and enforcement disabled for shadow/advisory observation.
3. Run the readiness, API workflow, migration, and frontend contract checks.
4. Set `SELECTIVE_INTEGRATION_ENFORCED=true` for a narrow internal cohort.
5. Expand only after monitoring shows no invariant violations.

When enforcement is on, legacy review-decision and packet-outcome write paths require the governed packet lifecycle. The packet decision endpoint is always fail-closed.

## Verification

```powershell
python scripts/verify-migrations.py
python scripts/verify-selective-integration.py
python packages/evals/run_selective_integration.py
python -m pytest tests/test_selective_integration.py -q
cd services/api
uv run --frozen pytest tests/test_selective_integration_workflow.py -q
cd ../../apps/web
npm.cmd run test:e2e -- --project=chromium
```

Frontend contract check without package-manager bootstrap:

```powershell
.\apps\web\node_modules\.bin\tsc.CMD -p apps\web\tsconfig.json --noEmit
```

The deterministic evaluation has six cases: governed happy path, missing risk, stale data, contradictory evidence, audit tampering, and future-outcome leakage. It is explicitly synthetic and does not establish investment performance.

## Operational evidence still required

The code-level roadmap is implemented, but the following environment-dependent release gates cannot be manufactured locally:

- apply and rollback `v0007` against staging PostgreSQL;
- run concurrent audit and memory writes against PostgreSQL;
- observe a shadow-mode cohort under real provider latency and failure behavior;
- rehearse feature-flag rollback;
- obtain security, data-license, risk-policy, and release-owner approvals.

These are deployment certifications, not missing application code. Production enforcement should remain off until they are recorded.
