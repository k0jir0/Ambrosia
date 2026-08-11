# Assisted Password Reset Runbook

## Purpose

Use this runbook when standard email-based password recovery is unavailable and
an authenticated support operator must issue a one-time reset link.

## Preconditions

1. Environment is non-production, or production explicitly enables assisted reset.
2. Operator is authenticated as `owner`, `admin`, or `service` role.
3. A support ticket exists and includes user verification evidence.

## Identity Verification Checklist

1. Confirm claimant controls the account email mailbox or verified backup channel.
2. Confirm recent account activity details (last successful sign-in date/time).
3. Confirm organization membership context (organization name and role).
4. Record verification method and result in the ticket before issuing a reset link.

## API Procedure

1. Sign in as a qualified support operator.
2. Capture CSRF token from the authenticated session.
3. Call `POST /auth/assisted-password-reset` with:
   - `email`
   - `ticketId`
   - `reason`
4. If the response includes `resetUrl`, deliver it only through the verified
   channel associated with the claimant.

## Response and Security Expectations

1. Endpoint always returns a generic message to avoid unintended account
   disclosure behavior.
2. Reset links are single-use and expire according to token TTL.
3. After successful reset, all existing sessions are revoked.

## Required Audit Fields

1. Operator identity (`actor`) and role.
2. Ticket ID.
3. Recovery reason.
4. Target account email.
5. Issuance timestamp.
6. Completion timestamp (written when reset is successfully consumed).

## Failure Handling

1. If assisted reset is disabled, return to fail-closed behavior and do not
   issue manual credentials.
2. If token is not consumed before expiry, require a new operator request and
   repeat verification.
3. If suspicious activity is detected, suspend reset and escalate to incident
   response.