# SES Production Access Request Template

## Purpose

Use this template when opening or responding to an AWS SES support case for production sending access tied to transactional account security email.

## Submission Draft

Subject: Request for SES production sending access for transactional security email

Hello AWS Support,

We are requesting SES production sending access for Ambrosia. Our email traffic is strictly transactional and user-initiated.

### 1. Use cases

- Account verification
- Password reset
- Team invitation

We do not send marketing campaigns, newsletters, or cold outreach through SES.

### 2. Recipient source and consent

- Recipients are first-party users who directly sign up or are invited by organization administrators.
- We do not use purchased or scraped lists.
- Address quality controls and rate limits are enforced in our authentication endpoints.

### 3. Authentication and alignment

- Verified SES identity configured in the target region
- DKIM enabled
- SPF aligned
- DMARC published and monitored
- Consistent sender address for transactional mail

### 4. Deliverability and abuse controls

- Account-level suppression is enabled
- Bounce, complaint, and reject events are captured and triaged
- One-time, short-lived reset tokens are used for password recovery
- Successful password resets revoke existing sessions

### 5. Operational ownership

- Named incident owner for email abuse and deliverability
- Complaint and bounce triage SLA documented
- Audit evidence retained for support review

### 6. Requested scope

- Initial conservative sending quota suitable for low-volume transactional traffic
- Planned warm-up with periodic reputation review and phased increase requests

### 7. Evidence attached

- Identity verification proof (domain/email)
- DKIM/SPF/DMARC records
- Sandbox send validation
- Suppression and event-handling runbook
- Volume ramp plan (30/60/90 days)

Thank you.
