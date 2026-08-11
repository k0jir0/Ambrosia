# SES Warm-Up 30/60/90 Plan

## Goal

Build sender reputation safely after SES production access is approved, while keeping complaint and bounce rates low.

## Day 0 Prerequisites

1. AUTH_EMAIL_MODE=ses
2. AUTH_EMAIL_FROM and AUTH_SES_IDENTITY_ARN configured
3. AUTH_SES_CONFIGURATION_SET configured
4. Bounce/complaint/reject event ingestion verified
5. Suppression policies enabled

## 30-Day Phase

1. Keep volume low and stable
2. Restrict traffic to verification/reset/invitation only
3. Review daily:
- send success rate
- hard bounces
- complaints
- reject events
4. Pause increases if abnormal signals appear

## 60-Day Phase

1. Increase volume gradually if metrics remain healthy
2. Keep complaint and bounce response times within SLA
3. Validate that operational runbook actions are consistently executed
4. Prepare evidence summary for AWS follow-up if higher quota is needed

## 90-Day Phase

1. Continue controlled growth
2. Keep recipient quality controls strict
3. Submit incremental limit increase request with measured history
4. Archive reputation and incident metrics for governance review

## Stop Conditions

1. Complaint spike beyond internal threshold
2. Hard bounce spike indicating recipient quality drift
3. Event ingestion or suppression path failure

When a stop condition triggers, freeze ramp-up and execute incident triage before resuming.
