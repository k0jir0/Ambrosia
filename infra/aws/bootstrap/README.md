# AWS staging bootstrap

These CloudFormation templates create the resources that cannot safely be
created by the application Terraform root itself. They do not deploy Ambrosia.
Run them from a governed non-production AWS account using a named federated
administrator role—never root credentials or long-lived GitHub access keys.

Prerequisites are an existing public Route53 hosted zone, an approved apex
domain, a globally unique state bucket name, a named owner/cost center, and an
approved monthly budget. Account-level CloudTrail, Config, GuardDuty, IAM
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
    DomainName=<apex-domain> `
    HostedZoneId=<public-zone-id> `
    BudgetEmail=<billing-owner-email> `
    MonthlyBudgetUsd=<approved-usd-limit> `
    Owner=<owner> `
    CostCenter=<cost-center> `
    DataClassification=synthetic
```

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
