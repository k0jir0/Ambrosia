# Index95 Phase 6: Service Account Lifecycle Runbook

## Scope

This runbook covers creation, usage, scope minimization, rotation, revocation, and audit export for Ambrosia enterprise service accounts.

## 1. Create Service Account

Example:

```bash
ambrosia --json enterprise service-account --name ci-bot --scopes public:read,advanced:read
```

Controls:

- Use least-privilege scopes.
- Do not share service account tokens across teams.
- Record owner, purpose, and expiration policy in internal inventory.

## 2. Validate and Store Token

- Store token in CI secret manager, not source control.
- Use environment variable injection at runtime.
- Validate access with read-only endpoint first.

## 3. Rotation (Scheduled)

Example:

```bash
ambrosia --json enterprise service-account-rotate svc-123 --rotated-by platform-ci
```

Rotation policy:

- Rotate every 30 days for production integrations.
- Rotate immediately after maintainer departure or compromise signal.
- Verify old token revocation after rollout.

## 4. Revocation (Emergency or Decommission)

Example:

```bash
ambrosia --json enterprise service-account-revoke svc-123
```

Triggers:

- Suspected credential leak.
- Unowned account.
- Scope escalation without approval.

## 5. Audit Export and Evidence

Example:

```bash
ambrosia --json enterprise audit-export --requested-by security --scope all
```

Required evidence:

- Rotation timestamp.
- Rotated-by actor.
- Revocation timestamp (if applicable).
- Scope set before and after lifecycle change.

## 6. Weekly Governance Checklist

- List all service accounts:

```bash
ambrosia --json enterprise service-accounts
```

- Verify no stale accounts.
- Verify no over-broad scopes.
- Verify rotation SLA compliance.
- Export audit packet for governance archive.

## 7. Incident Response Notes

- Revoke compromised account first, then investigate usage logs.
- Issue replacement account with reduced scope.
- Regenerate dependent CI/CD secrets.
- Document blast radius and corrective actions.
