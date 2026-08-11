# Index153 Evidence Manifest

This manifest lists concrete implementation evidence for SES re-evaluation.

## Product and Security Flow Evidence

1. Assisted reset endpoint and guardrails:
- services/api/app/auth_api.py

2. Assisted reset durable audit sink events:
- services/api/app/identity.py
- services/api/app/main.py

3. Standard forgot-password fail-closed behavior and non-enumeration posture:
- services/api/app/auth_api.py

4. Forgot-password fallback UX guidance:
- apps/web/src/components/auth-pages.tsx

## Operational Readiness Evidence

1. Email readiness endpoint:
- services/api/app/operations.py
- Route: GET /operational/email-readiness

2. Readiness validation test:
- services/api/tests/test_index119_operations.py

3. Assisted reset validation tests:
- services/api/tests/test_identity.py

## SES and Monitoring Evidence

1. SES identity/configuration set/event destination definitions:
- infra/aws/main.tf

2. SES alarms (bounce rate, complaint rate, reject count):
- infra/aws/main.tf

## Governance Artifacts

1. SES request template:
- docs/operations/SES_PRODUCTION_ACCESS_REQUEST_TEMPLATE.md

2. Warm-up plan:
- docs/operations/SES_WARMUP_30_60_90_PLAN.md

3. Deliverability SLO/SLA:
- docs/operations/SES_DELIVERABILITY_SLO_AND_SLA.md

4. Assisted reset runbook:
- docs/operations/ASSISTED_PASSWORD_RESET_RUNBOOK.md

## Suggested Validation Commands

1. Focused tests:
- C:/Users/ryanv/AppData/Local/Programs/Python/Python312/python.exe -m pytest services/api/tests/test_identity.py services/api/tests/test_index119_operations.py -q

2. Optional readiness API check (requires authenticated token):
- GET /operational/email-readiness

## External Dependencies (Not automatable in-repo)

1. AWS support-case submission/response cycle.
2. SES production approval decision.
3. Post-approval reputation warm-up window outcomes.
