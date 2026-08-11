# SES Deliverability SLO and Incident SLA

## Objective

Define measurable service targets and response SLAs for transactional security email.

## Service Scope

1. Account verification messages
2. Password reset messages
3. Team invitation messages

## SLO Targets

1. Transactional delivery path available when SES is approved and configured
2. Reset and verification events processed without user enumeration leakage
3. Event ingestion for bounce/complaint/reject operational and monitored

## Incident SLA

1. Critical deliverability outage
- Acknowledge: 15 minutes
- Initial triage: 30 minutes
- Mitigation decision: 60 minutes

2. Complaint or bounce anomaly
- Acknowledge: 30 minutes
- Root-cause triage: 4 hours
- Corrective action: same business day

## Required Runbook Actions

1. Freeze send-volume increase while incident is active
2. Confirm suppression is functioning
3. Validate sender alignment and recent config changes
4. Document incident timeline and recovery evidence

## Evidence Retention

1. Keep audit logs for assisted resets and auth events
2. Keep SES event samples and aggregated trend snapshots
3. Keep support-case references and remediation notes
