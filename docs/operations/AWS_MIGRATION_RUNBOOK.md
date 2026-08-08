# Render-to-AWS migration and rollback runbook

This runbook implements the Index132 migration sequence and Index133 AWS
staging control plane. It is an operator
procedure, not evidence that a deployment has occurred. Every execution must
attach timestamps, command output, checksums, approvers, and incident links to a
copy of `index132-external-evidence.template.json` stored in the controlled
release evidence system.

## Authority and stop conditions

The release commander, database operator, security reviewer, and product owner
must be named before a rehearsal or cutover. Stop immediately on a cross-tenant
read/write, checksum or row-count mismatch, irreversible migration, unavailable
rollback backup, failed `/ready`, audit persistence failure, unexplained error
budget burn, or evidence that source data changed outside the declared window.

Targets are RPO <= 15 minutes and RTO <= 60 minutes until measured evidence
justifies different objectives. No operator may paste credentials into a log,
issue, JSON evidence file, shell history, or screenshot.

## 1. Inventory the real Render system

1. Copy `render-inventory.template.json` into the access-controlled evidence
   location. Read the Render dashboard and fill every field; `render.yaml` is
   only a hypothesis.
2. Capture service IDs, regions, plans, deploy commits, custom domains, health
   paths, build/start commands, environment-variable names (never values),
   database version/storage/extensions, backup time, DNS provider/TTL, and all
   background or scheduled work.
3. Export dashboard and DNS screenshots with secrets redacted. Record their
   SHA-256 digests.
4. Reconcile the inventory against `render.yaml`, runtime `/ready`, and the
   database inventory. Resolve every difference before rehearsal one.

## 2. Bootstrap AWS staging

1. Create a dedicated AWS account or approved workload boundary and configure
   IAM Identity Center, CloudTrail/Config/GuardDuty/Access Analyzer, alternate
   contacts, quotas, Cost Anomaly Detection, and an approved monthly budget.
   Deploy `infra/aws/bootstrap/control-plane.yaml` in `ca-central-1`; it creates
   KMS-encrypted/versioned state with a seven-day release-plan lifecycle,
   GitHub OIDC trust scoped to `repo:k0jir0/Ambrosia:environment:staging`, a
   bounded deploy role, budget thresholds, and the regional ALB certificate.
2. Deploy `infra/aws/bootstrap/edge-certificate.yaml` in `us-east-1`. Wait for
   both ACM certificates to be `ISSUED`. The regional certificate covers
   `api-staging` and `origin-staging`; the edge certificate covers `staging`.
3. Run `scripts/configure-github-aws-staging.ps1` to create a reviewed,
   staging-branch-only GitHub environment and branch protection. If the private
   repository's billing plan rejects environment reviewers, use
   `-AllowPlanLimitedEnvironment` explicitly; this disables administrator
   deployment bypass, retains the staging-only environment policy, and requires
   independent approval at the protected `staging` branch instead. Populate
   environment variables `AWS_ACCOUNT_ID`, `AWS_REGION`, `TF_STATE_BUCKET`,
   `TF_STATE_KMS_KEY_ARN`, `DOMAIN_NAME`, `HOSTED_ZONE_ID`,
   `API_DESIRED_COUNT`, `WEB_DESIRED_COUNT`, `ALERT_EMAIL`, `OWNER`,
   `COST_CENTER`, `DATA_CLASSIFICATION`, and `BUDGET_NAME`; add protected secrets
   `AWS_DEPLOY_ROLE_ARN`, `ALB_CERTIFICATE_ARN`, and
   `CLOUDFRONT_CERTIFICATE_ARN`. Re-run the script with `-VerifyOnly` (and the
   same plan-limitation switch, when used) and retain its value-free output.
4. Review `infra/aws/environments/staging.tfvars.example`, run `terraform fmt`,
   `init`, `validate`, and a saved plan. A second operator reviews the plan.
5. Record the exact merged `staging` SHA. Dispatch **AWS release** with
   `environment=staging`, `apply=true`, `candidate_sha=<exact-staging-sha>`, and
   `ref=staging`. The workflow asserts repository/ref/SHA/account/region/domain,
   budget, state, certificates, and capacity; builds both containers; blocks on
   fixed high/critical vulnerabilities; emits SPDX SBOMs; resolves and signs
   immutable ECR digests; then stores a value-free foundation-plan summary and
   the sensitive binary plan only in protected state storage.
6. Review and approve the saved foundation plan. It applies ECS services at
   zero and does not register Application Auto Scaling. After the one-off
   migration exits zero, review and approve the separate service-enablement
   plan. The final job enables services, waits for ECS stability, and verifies
   `/api/ready` and the website root. Stop on any unexplained replacement of
   RDS, Redis, KMS, Route53, identity, or state resources.
7. Verify the task definitions contain `repository@sha256:...`, not a tag.
   Preserve Terraform plan/apply logs, image digests, signatures, SBOMs, ECS
   task ARNs, and `/ready` output.

## 3. Database rehearsal (perform twice)

Use a fresh, isolated RDS target for each rehearsal. The source remains
read-only from the migration operator’s perspective.

1. Record PostgreSQL client/server versions and source inventory. Create a
   Render backup immediately before export.
2. Export over TLS using a credential supplied by the secret manager:

   ```bash
   pg_dump "$RENDER_DATABASE_URL" --format=custom --no-owner --no-acl \
     --file="ambrosia-render-REHEARSAL.dump"
   sha256sum "ambrosia-render-REHEARSAL.dump"
   ```

3. Restore into an empty target owned by the migration administrator:

   ```bash
   pg_restore --dbname="$AWS_DATABASE_ADMIN_URL" --no-owner --no-acl \
     --exit-on-error --single-transaction "ambrosia-render-REHEARSAL.dump"
   RUNTIME_DATABASE_USER=ambrosia_app \
   RUNTIME_DATABASE_PASSWORD="$RUNTIME_DATABASE_PASSWORD" \
   uv run --project services/api --frozen python scripts/migrate_database.py
   ```

4. Compare source and target with read-only transactions:

   ```bash
   RENDER_DATABASE_URL="$RENDER_DATABASE_URL" AWS_DATABASE_URL="$AWS_DATABASE_ADMIN_URL" \
   uv run --project services/api --frozen python scripts/validate_migration.py \
     --output artifacts/migration-validation-rehearsal-N.json
   ```

5. Run the entire release test suite, PostgreSQL tenant tests, signup/login/
   reset/invitation journeys, packet/review/outcome/export workflows, audit
   verification, load test, fault test, and a backup restore into a second
   isolated database.
6. Confirm every legacy tenant-owned row is assigned only to the quarantine
   organization and is invisible to newly signed-up tenants.
7. Record elapsed export, restore, migration, validation, and recovery times.
   Rehearsals one and two must produce the same counts and invariant results.

## 4. Rollback rehearsal

1. Before changing traffic, prove the Render services still use the original
   Render database and the AWS staging services use only RDS.
2. Lower DNS TTL at least one prior TTL interval before the exercise.
3. Shift a canary hostname to AWS. Exercise the golden signup-to-saved-packet
   journey and synthetic monitors.
4. Simulate a declared stop condition. Freeze AWS writes, preserve logs, point
   the canary back to Render, and verify the old service is healthy within RTO.
5. If any writes reached AWS after the source freeze, treat the databases as
   divergent. Do not blindly reverse-sync. Reconcile via the approved event
   ledger or abandon those test writes under the rehearsal data policy.

## 5. Production cutover

1. Confirm two successful migration rehearsals, one rollback rehearsal, a
   verified restore, load/fault evidence, security and counsel approvals, SES
   production sending, and an approved GO record.
2. Announce maintenance. Disable governed writes on Render and verify the write
   probe is rejected. Record freeze time.
3. Take the final Render backup, export, checksum, restore to RDS, migrate, and
   run `validate_migration.py`. Any mismatch is NO-GO.
4. Start AWS services by immutable digest. Run `/live`, `/ready`, signup,
   verification email, login, password reset, team invite, golden packet,
   cross-tenant denial, audit, and object-prefix probes.
5. Shift a small canary, then staged traffic. Monitor 4xx/5xx, latency, ECS
   health, RDS connections/storage/replication, Redis, WAF, SES bounces/
   complaints, audit persistence, signup completion, and packet completion.
6. Keep Render deploy-frozen and recoverable during a minimum 72-hour bake.
   Keep `RENDER_ROLLBACK_DEPLOY_ENABLED` false except for an approved rollback.
7. After the formal GO, remove Render DNS, hooks, credentials, and service/data
   resources according to retention policy. Record deletion and recovery status.

## 6. Rollback decision during production

Rollback is straightforward only before post-freeze AWS writes. If no governed
writes occurred, return DNS to Render, re-enable its writes, verify health, and
publish the incident notice. If AWS accepted writes, stop both write paths and
invoke data reconciliation; the release commander must choose recovery from the
final Render backup plus audited AWS events or continued AWS repair. Never run
two writable primaries.

## 7. Evidence closure

Run `python scripts/generate-index132-readiness.py --external-evidence <approved-copy>
--require-release-ready`. A GO requires every passed external gate to contain at
least one evidence reference. Repository tests alone cannot satisfy deployment,
security-review, legal-review, usability, model-quality, bake, or paid-customer
gates.

Primary references: [AWS prescriptive guidance for PostgreSQL migration](https://docs.aws.amazon.com/prescriptive-guidance/latest/migration-postgresql-database/welcome.html), [AWS ECS deployment circuit breaker](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-circuit-breaker.html), [Render PostgreSQL backups](https://render.com/docs/postgresql-backups), and [PostgreSQL pg_dump](https://www.postgresql.org/docs/current/app-pgdump.html).
