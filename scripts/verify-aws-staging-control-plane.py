"""Fail closed when the Index133 AWS staging release contract regresses."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(text: str, fragment: str, label: str) -> None:
    if fragment not in text:
        raise SystemExit(f"AWS staging contract missing {label}: {fragment!r}")


def reject(text: str, fragment: str, label: str) -> None:
    if fragment in text:
        raise SystemExit(f"AWS staging contract permits {label}: {fragment!r}")


def main() -> None:
    workflow = (ROOT / ".github/workflows/aws-release.yml").read_text(encoding="utf-8")
    terraform = (ROOT / "infra/aws/main.tf").read_text(encoding="utf-8")
    variables = (ROOT / "infra/aws/variables.tf").read_text(encoding="utf-8")
    control_plane = (ROOT / "infra/aws/bootstrap/control-plane.yaml").read_text(
        encoding="utf-8"
    )
    compact_terraform = " ".join(terraform.split())

    for path in (
        ROOT / "infra/aws/bootstrap/control-plane.yaml",
        ROOT / "infra/aws/bootstrap/edge-certificate.yaml",
        ROOT / "infra/aws/bootstrap/README.md",
        ROOT / "scripts/configure-github-aws-staging.ps1",
    ):
        if not path.is_file():
            raise SystemExit(f"AWS staging bootstrap artifact is missing: {path.relative_to(ROOT)}")

    required_workflow_fragments = {
        "staging-only input": "options: [staging]",
        "manual candidate SHA": "candidate_sha:",
        "repository assertion": 'test "$GITHUB_REPOSITORY" = "k0jir0/Ambrosia"',
        "staging ref assertion": 'test "$GITHUB_REF_NAME" = "staging"',
        "account assertion": "aws sts get-caller-identity",
        "state encryption verification": "get-bucket-encryption",
        "native state locking": 'backend-config="use_lockfile=true"',
        "fixed vulnerability scan": "ignore-unfixed: true",
        "SPDX SBOM": "format: spdx-json",
        "digest resolution": "Resolve immutable ECR digests",
        "keyless signing": "cosign sign --yes",
        "foundation saved plan": 'PLAN_KEY="ambrosia/$DEPLOY_ENVIRONMENT/plans/',
        "value-free plan summary": "Terraform values are intentionally omitted",
        "migration exit gate": 'test "$EXIT_CODE" = "0"',
        "service enable saved plan": 'PLAN_PATH="$RUNNER_TEMP/enable.tfplan"',
        "public API readiness": 'curl --fail --retry 12 --retry-delay 10 "$API_URL/ready"',
        "budget precondition": "aws budgets describe-budget",
        "certificate precondition": "aws acm describe-certificate",
        "explicit API capacity": '-var="api_desired_count=$API_DESIRED_COUNT"',
        "explicit web capacity": '-var="web_desired_count=$WEB_DESIRED_COUNT"',
        "accountable owner": '-var="owner=$OWNER"',
        "cost allocation": '-var="cost_center=$COST_CENTER"',
    }
    for label, fragment in required_workflow_fragments.items():
        require(workflow, fragment, label)

    reject(workflow, "options: [staging, production]", "production selection in staging workflow")
    reject(workflow, "actions/upload-artifact", "broadly readable Terraform binary plan artifact")
    reject(workflow, "Sanitized Terraform plan output", "value-bearing textual plan summary")

    require(terraform, "aws_cloudfront_function", "same-origin API prefix rewrite")
    require(terraform, "request.uri.substring(4)", "FastAPI root-path forwarding")
    require(compact_terraform, "count = var.enable_services ? 1 : 0", "migration-safe autoscaling gate")
    require(compact_terraform, "desired_count = var.enable_services ?", "migration-safe service gate")
    require(compact_terraform, 'allowed_methods = ["GET", "HEAD", "OPTIONS"]', "web method restriction")
    require(compact_terraform, "DataClassification = var.data_classification", "data classification tags")
    require(variables, 'var.aws_region == "ca-central-1"', "approved region restriction")
    require(variables, '@sha256:[0-9a-f]{64}$', "immutable image validation")

    if control_plane.count("iam:CreateServiceLinkedRole") != 1:
        raise SystemExit(
            "AWS staging contract must contain exactly one service-linked-role creation grant"
        )
    for service_name in (
        "elasticloadbalancing.amazonaws.com",
        "rds.amazonaws.com",
        "elasticache.amazonaws.com",
    ):
        require(control_plane, service_name, f"{service_name} service-linked-role bootstrap")
    reject(
        control_plane,
        "iam::${AWS::AccountId}:role/aws-service-role/*",
        "unbounded service-linked-role creation",
    )

    print("AWS staging control plane contract verified.")


if __name__ == "__main__":
    main()
