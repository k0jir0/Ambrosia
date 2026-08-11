# AWS SES Support Update (Index153)

Use this message to update the existing SES support case.

## Subject

Request for SES production sending approval update for transactional account-security email

## Message Body

Hello AWS Support,

We are following up on our SES production sending request with concrete updates to our controls, monitoring, and operations.

Our SES usage is strictly transactional and user-initiated:
1. Account verification
2. Password reset
3. Team invitation

We do not send marketing campaigns, newsletters, or cold outreach through SES.

Since our previous request, we have implemented and validated the following:

### 1) Security and abuse controls
1. Password reset tokens are single-use and short-lived.
2. Password reset completion revokes prior sessions.
3. Forgot-password responses remain non-enumerating.
4. Auth endpoints are rate limited.

### 2) Operational safeguards
1. A controlled assisted-reset fallback exists for continuity when delivery is unavailable.
2. Assisted reset issuance is role-gated to privileged operators.
3. Assisted reset issuance/completion now emits durable audit events.

### 3) Deliverability and reputation controls
1. SES configuration set for transactional sends is defined.
2. Event destinations for SEND, DELIVERY, DELIVERY_DELAY, BOUNCE, COMPLAINT, REJECT, and RENDERING_FAILURE are configured.
3. CloudWatch alarms are defined for bounce rate, complaint rate, and reject count.
4. Suppression and incident-response procedures are documented.

### 4) Readiness and governance evidence
1. Machine-readable operational email readiness endpoint implemented.
2. 30/60/90 warm-up plan documented.
3. Deliverability SLO and incident SLA documented.
4. Assisted password reset runbook documented.

We are requesting a conservative initial production quota suitable for low-volume transactional security email, with a controlled warm-up and periodic review.

If helpful, we can provide additional evidence artifacts and logs from our readiness checks and test validations.

Thank you for re-evaluating our request.

## Suggested Attachments

1. docs/operations/SES_PRODUCTION_ACCESS_REQUEST_TEMPLATE.md
2. docs/operations/SES_WARMUP_30_60_90_PLAN.md
3. docs/operations/SES_DELIVERABILITY_SLO_AND_SLA.md
4. docs/operations/ASSISTED_PASSWORD_RESET_RUNBOOK.md
5. docs/operations/INDEX153_EVIDENCE_MANIFEST.md
