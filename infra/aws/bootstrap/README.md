# AWS staging bootstrap

These CloudFormation templates create the resources that cannot safely be
created by the application Terraform root itself. They do not deploy Ambrosia.
Run them from a governed non-production AWS account using a named federated
administrator role—never root credentials or long-lived GitHub access keys.

Custom-domain deployments require an existing public Route53 hosted zone and
approved apex domain. Initial staging may instead set
`CustomDomainEnabled=false` and use the generated CloudFront HTTPS hostname;
the regional and edge certificates are then intentionally omitted. Every path
still requires a globally unique state bucket name, named owner/cost center,
and approved monthly budget. Account-level CloudTrail, Config, GuardDuty, IAM
Access Analyzer, Cost Anomaly Detection, security contacts, and service quotas
remain organization controls and must be verified separately.

Deploy the control plane in `ca-central-1`:

```powershell
aws cloudformation deploy `
  --region ca-central-1 `
  --stack-name ambrosia-staging-control-plane `
  --template-file infra/aws/bootstrap/control-plane.yaml `
  --capabilities CAPABILITY_NAMED_IAM `
  --parameter-overrides `
    StateBucketName=<globally-unique-bucket> `
    CustomDomainEnabled=true `
    DomainName=<apex-domain> `
    HostedZoneId=<public-zone-id> `
    ExistingBudgetName="" `
    BudgetEmail=<billing-owner-email> `
    MonthlyBudgetUsd=<approved-usd-limit> `
    Owner=<owner> `
    CostCenter=<cost-center> `
    DataClassification=synthetic
```

For generated-hostname staging, omit `DomainName` and `HostedZoneId`, set
`CustomDomainEnabled=false`, and do not deploy the edge-certificate stack.
Signup exposes its single-use development verification link in staging because
SES domain identity cannot be established before a domain is selected.
If a governed AWS budget already exists, pass its exact name as
`ExistingBudgetName` and omit `BudgetEmail`; the release workflow still fails
closed unless that budget can be described in the target account.

Deploy the edge certificate separately in `us-east-1`:

```powershell
aws cloudformation deploy `
  --region us-east-1 `
  --stack-name ambrosia-staging-edge-certificate `
  --template-file infra/aws/bootstrap/edge-certificate.yaml `
  --parameter-overrides `
    DomainName=<apex-domain> `
    HostedZoneId=<public-zone-id> `
    Owner=<owner> `
    CostCenter=<cost-center>
```

Wait for both stacks to finish and both certificates to report `ISSUED`. Read
stack outputs, configure the protected GitHub `staging` environment with
`scripts/configure-github-aws-staging.ps1`, then run its `-VerifyOnly` mode.

The deployment role is deliberately not `AdministratorAccess`; it is limited
to the staging state path, hosted zone, Ambrosia role and artifact-bucket name
prefixes, and the AWS service APIs declared by `infra/aws`. Review CloudTrail
and IAM Access Analyzer after the first apply and reduce create-time wildcard
permissions where AWS has exposed stable resource ARNs.

Do not delete either stack casually. The KMS key and state bucket are retained
if the control-plane stack is deleted. Recovery or deliberate destruction must
be performed through an approved, recorded break-glass procedure.
