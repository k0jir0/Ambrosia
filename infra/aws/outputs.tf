output "web_url" {
  value = local.public_web_url
}

output "api_url" {
  value = "${local.public_web_url}/api"
}

output "ecs_cluster" {
  value = aws_ecs_cluster.main.name
}

output "database_secret_arn" {
  value     = aws_secretsmanager_secret.database_url.arn
  sensitive = true
}

output "migration_task_definition" {
  value = aws_ecs_task_definition.migration.arn
}

output "application_subnet_ids" {
  value = aws_subnet.application[*].id
}

output "ecs_security_group_id" {
  value = aws_security_group.ecs.id
}

output "artifact_bucket" {
  value = aws_s3_bucket.artifacts.id
}

output "api_ecr_repository" {
  value = aws_ecr_repository.api.repository_url
}

output "web_ecr_repository" {
  value = aws_ecr_repository.web.repository_url
}

output "ses_dkim_tokens" {
  value = local.custom_domain ? aws_sesv2_email_identity.domain[0].dkim_signing_attributes[0].tokens : []
}
