data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled"
}

data "aws_cloudfront_origin_request_policy" "all_except_host" {
  name = "Managed-AllViewerExceptHostHeader"
}

data "aws_ec2_managed_prefix_list" "cloudfront_origin" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

locals {
  name                    = "${var.project}-${var.environment}"
  production              = var.environment == "production"
  custom_domain           = var.custom_domain_enabled
  configured_web_hostname = local.custom_domain ? (local.production ? var.domain_name : "staging.${var.domain_name}") : ""
  api_hostname            = local.custom_domain ? (local.production ? "api.${var.domain_name}" : "api-staging.${var.domain_name}") : ""
  origin_hostname         = local.custom_domain ? (local.production ? "origin.${var.domain_name}" : "origin-staging.${var.domain_name}") : ""
  public_web_url          = local.custom_domain ? "https://${local.configured_web_hostname}" : "https://${aws_cloudfront_distribution.web.domain_name}"
  tags = {
    Project            = var.project
    Environment        = var.environment
    ManagedBy          = "terraform"
    Roadmap            = "index133"
    Owner              = var.owner
    CostCenter         = var.cost_center
    DataClassification = var.data_classification
  }
}

resource "aws_ecr_repository" "api" {
  name                 = "${local.name}-api"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }
}

resource "aws_ecr_repository" "web" {
  name                 = "${local.name}-web"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }
}

resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name
  policy = jsonencode({ rules = [{
    rulePriority = 1
    description  = "Retain the newest 40 immutable images"
    selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 40 }
    action       = { type = "expire" }
  }] })
}

resource "aws_ecr_lifecycle_policy" "web" {
  repository = aws_ecr_repository.web.name
  policy     = aws_ecr_lifecycle_policy.api.policy
}

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${local.name}-vpc" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${local.name}-igw" }
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index)
  map_public_ip_on_launch = false
  tags                    = { Name = "${local.name}-public-${count.index + 1}" }
}

resource "aws_subnet" "application" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  availability_zone = data.aws_availability_zones.available.names[count.index]
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + 4)
  tags              = { Name = "${local.name}-app-${count.index + 1}" }
}

resource "aws_subnet" "data" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  availability_zone = data.aws_availability_zones.available.names[count.index]
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + 8)
  tags              = { Name = "${local.name}-data-${count.index + 1}" }
}

resource "aws_eip" "nat" {
  count  = local.production ? 2 : 1
  domain = "vpc"
  tags   = { Name = "${local.name}-nat-${count.index + 1}" }
}

resource "aws_nat_gateway" "main" {
  count         = local.production ? 2 : 1
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  depends_on    = [aws_internet_gateway.main]
  tags          = { Name = "${local.name}-nat-${count.index + 1}" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  tags = { Name = "${local.name}-public" }
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "application" {
  count  = 2
  vpc_id = aws_vpc.main.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[local.production ? count.index : 0].id
  }
  tags = { Name = "${local.name}-application-${count.index + 1}" }
}

resource "aws_route_table_association" "application" {
  count          = 2
  subnet_id      = aws_subnet.application[count.index].id
  route_table_id = aws_route_table.application[count.index].id
}

resource "aws_route_table" "data" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${local.name}-data" }
}

resource "aws_route_table_association" "data" {
  count          = 2
  subnet_id      = aws_subnet.data[count.index].id
  route_table_id = aws_route_table.data.id
}

resource "aws_security_group" "alb" {
  name        = "${local.name}-alb"
  description = "CloudFront origin ingress only"
  vpc_id      = aws_vpc.main.id
  ingress {
    description     = local.custom_domain ? "CloudFront HTTPS origin" : "CloudFront HTTP origin"
    from_port       = local.custom_domain ? 443 : 80
    to_port         = local.custom_domain ? 443 : 80
    protocol        = "tcp"
    prefix_list_ids = [data.aws_ec2_managed_prefix_list.cloudfront_origin.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "ecs" {
  name        = "${local.name}-ecs"
  description = "Only the ALB may reach application containers"
  vpc_id      = aws_vpc.main.id
  ingress {
    from_port       = 3000
    to_port         = 3000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "database" {
  name        = "${local.name}-database"
  description = "PostgreSQL from ECS only"
  vpc_id      = aws_vpc.main.id
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }
}

resource "aws_security_group" "redis" {
  name        = "${local.name}-redis"
  description = "TLS Redis from ECS only"
  vpc_id      = aws_vpc.main.id
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }
}

resource "aws_db_subnet_group" "main" {
  name       = local.name
  subnet_ids = aws_subnet.data[*].id
}

resource "aws_elasticache_subnet_group" "main" {
  name       = local.name
  subnet_ids = aws_subnet.data[*].id
}

resource "random_password" "database" {
  length  = 36
  special = false
}

resource "random_password" "database_runtime" {
  length  = 36
  special = false
}

resource "random_password" "redis" {
  length  = 40
  special = false
}

resource "random_password" "token_pepper" {
  length  = 64
  special = false
}

resource "aws_db_parameter_group" "postgres" {
  name   = "${local.name}-pg16"
  family = "postgres16"
  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
}

resource "aws_db_instance" "postgres" {
  identifier                      = "${local.name}-postgres"
  engine                          = "postgres"
  engine_version                  = "16"
  instance_class                  = var.db_instance_class
  allocated_storage               = 30
  max_allocated_storage           = 200
  storage_type                    = "gp3"
  storage_encrypted               = true
  db_name                         = "ambrosia"
  username                        = "ambrosia_admin"
  password                        = random_password.database.result
  port                            = 5432
  multi_az                        = local.production
  publicly_accessible             = false
  db_subnet_group_name            = aws_db_subnet_group.main.name
  vpc_security_group_ids          = [aws_security_group.database.id]
  parameter_group_name            = aws_db_parameter_group.postgres.name
  backup_retention_period         = local.production ? 35 : 7
  copy_tags_to_snapshot           = true
  deletion_protection             = local.production
  skip_final_snapshot             = !local.production
  final_snapshot_identifier       = local.production ? "${local.name}-final" : null
  performance_insights_enabled    = true
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  auto_minor_version_upgrade      = true
  apply_immediately               = false
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "${local.name}-redis"
  description                = "Ambrosia cache and coordination"
  engine                     = "redis"
  node_type                  = var.redis_node_type
  port                       = 6379
  num_cache_clusters         = local.production ? 2 : 1
  automatic_failover_enabled = local.production
  multi_az_enabled           = local.production
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = random_password.redis.result
  subnet_group_name          = aws_elasticache_subnet_group.main.name
  security_group_ids         = [aws_security_group.redis.id]
  snapshot_retention_limit   = local.production ? 7 : 1
  apply_immediately          = false
}

resource "aws_secretsmanager_secret" "database_url" {
  name                    = "${local.name}/database-url"
  recovery_window_in_days = local.production ? 30 : 0
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id     = aws_secretsmanager_secret.database_url.id
  secret_string = "postgresql://ambrosia_app:${random_password.database_runtime.result}@${aws_db_instance.postgres.address}:${aws_db_instance.postgres.port}/${aws_db_instance.postgres.db_name}?sslmode=require"
}

resource "aws_secretsmanager_secret" "database_admin_url" {
  name                    = "${local.name}/database-admin-url"
  recovery_window_in_days = local.production ? 30 : 0
}

resource "aws_secretsmanager_secret_version" "database_admin_url" {
  secret_id     = aws_secretsmanager_secret.database_admin_url.id
  secret_string = "postgresql://${aws_db_instance.postgres.username}:${random_password.database.result}@${aws_db_instance.postgres.address}:${aws_db_instance.postgres.port}/${aws_db_instance.postgres.db_name}?sslmode=require"
}

resource "aws_secretsmanager_secret" "database_runtime_password" {
  name                    = "${local.name}/database-runtime-password"
  recovery_window_in_days = local.production ? 30 : 0
}

resource "aws_secretsmanager_secret_version" "database_runtime_password" {
  secret_id     = aws_secretsmanager_secret.database_runtime_password.id
  secret_string = random_password.database_runtime.result
}

resource "aws_secretsmanager_secret" "redis_url" {
  name                    = "${local.name}/redis-url"
  recovery_window_in_days = local.production ? 30 : 0
}

resource "aws_secretsmanager_secret_version" "redis_url" {
  secret_id     = aws_secretsmanager_secret.redis_url.id
  secret_string = "rediss://:${random_password.redis.result}@${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379/0"
}

resource "aws_secretsmanager_secret" "token_pepper" {
  name                    = "${local.name}/auth-token-pepper"
  recovery_window_in_days = local.production ? 30 : 0
}

resource "aws_secretsmanager_secret_version" "token_pepper" {
  secret_id     = aws_secretsmanager_secret.token_pepper.id
  secret_string = random_password.token_pepper.result
}

resource "aws_s3_bucket" "artifacts" {
  bucket_prefix = "${local.name}-artifacts-"
}

resource "aws_kms_key" "artifacts" {
  description             = "Ambrosia governed artifact encryption"
  enable_key_rotation     = true
  deletion_window_in_days = local.production ? 30 : 7
}

resource "aws_kms_alias" "artifacts" {
  name          = "alias/${local.name}-artifacts"
  target_key_id = aws_kms_key.artifacts.key_id
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.artifacts.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    id     = "governed-retention"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload { days_after_initiation = 7 }
    noncurrent_version_expiration { noncurrent_days = local.production ? 365 : 30 }
  }
}

resource "aws_s3_bucket_policy" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.artifacts.arn, "${aws_s3_bucket.artifacts.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
}

resource "aws_sesv2_email_identity" "domain" {
  count          = local.custom_domain ? 1 : 0
  email_identity = var.domain_name
}

resource "aws_ses_domain_mail_from" "domain" {
  count                  = local.custom_domain ? 1 : 0
  domain                 = var.domain_name
  mail_from_domain       = "mail.${var.domain_name}"
  behavior_on_mx_failure = "RejectMessage"
  depends_on             = [aws_sesv2_email_identity.domain]
}

resource "aws_route53_record" "ses_mail_from_mx" {
  count   = local.custom_domain ? 1 : 0
  zone_id = var.hosted_zone_id
  name    = aws_ses_domain_mail_from.domain[0].mail_from_domain
  type    = "MX"
  ttl     = 300
  records = ["10 feedback-smtp.${var.aws_region}.amazonses.com"]
}

resource "aws_route53_record" "ses_mail_from_spf" {
  count   = local.custom_domain ? 1 : 0
  zone_id = var.hosted_zone_id
  name    = aws_ses_domain_mail_from.domain[0].mail_from_domain
  type    = "TXT"
  ttl     = 300
  records = ["v=spf1 include:amazonses.com ~all"]
}

resource "aws_route53_record" "ses_dkim" {
  count   = local.custom_domain ? 3 : 0
  zone_id = var.hosted_zone_id
  name    = "${aws_sesv2_email_identity.domain[0].dkim_signing_attributes[0].tokens[count.index]}._domainkey.${var.domain_name}"
  type    = "CNAME"
  ttl     = 300
  records = ["${aws_sesv2_email_identity.domain[0].dkim_signing_attributes[0].tokens[count.index]}.dkim.amazonses.com"]
}

resource "aws_sesv2_configuration_set" "transactional" {
  configuration_set_name = "${local.name}-transactional"
  reputation_options { reputation_metrics_enabled = true }
  sending_options { sending_enabled = true }
}

resource "aws_sns_topic" "ses_events" {
  name = "${local.name}-ses-events"
}

resource "aws_sns_topic_policy" "ses_events" {
  arn = aws_sns_topic.ses_events.arn
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowSesEvents"
      Effect    = "Allow"
      Principal = { Service = "ses.amazonaws.com" }
      Action    = "sns:Publish"
      Resource  = aws_sns_topic.ses_events.arn
      Condition = {
        StringEquals = { "AWS:SourceAccount" = data.aws_caller_identity.current.account_id }
        ArnLike      = { "AWS:SourceArn" = aws_sesv2_configuration_set.transactional.arn }
      }
    }]
  })
}

resource "aws_sesv2_configuration_set_event_destination" "transactional" {
  configuration_set_name = aws_sesv2_configuration_set.transactional.configuration_set_name
  event_destination_name = "bounce-complaint-reject"
  event_destination {
    enabled              = true
    matching_event_types = ["BOUNCE", "COMPLAINT", "REJECT"]
    sns_destination { topic_arn = aws_sns_topic.ses_events.arn }
  }
}

resource "aws_route53_record" "dmarc" {
  count   = local.custom_domain ? 1 : 0
  zone_id = var.hosted_zone_id
  name    = "_dmarc.${var.domain_name}"
  type    = "TXT"
  ttl     = 300
  records = ["v=DMARC1; p=none; rua=mailto:dmarc@${var.domain_name}; adkim=s; aspf=s"]
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${local.name}/api"
  retention_in_days = local.production ? 90 : 30
}

resource "aws_cloudwatch_log_group" "web" {
  name              = "/ecs/${local.name}/web"
  retention_in_days = local.production ? 90 : 30
}

resource "aws_iam_role" "ecs_execution" {
  name = "${local.name}-ecs-execution"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_secrets" {
  name = "read-runtime-secrets"
  role = aws_iam_role.ecs_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["secretsmanager:GetSecretValue"]
      Resource = [
        aws_secretsmanager_secret.database_url.arn,
        aws_secretsmanager_secret.database_admin_url.arn,
        aws_secretsmanager_secret.database_runtime_password.arn,
        aws_secretsmanager_secret.redis_url.arn,
        aws_secretsmanager_secret.token_pepper.arn,
      ]
    }]
  })
}

resource "aws_iam_role" "ecs_task" {
  name = "${local.name}-ecs-task"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "ecs_task" {
  name = "application-boundaries"
  role = aws_iam_role.ecs_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      local.custom_domain ? [{
        Effect   = "Allow"
        Action   = ["ses:SendEmail"]
        Resource = [aws_sesv2_email_identity.domain[0].arn]
      }] : [],
      [
        {
          Effect   = "Allow"
          Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
          Resource = ["${aws_s3_bucket.artifacts.arn}/*"]
        },
        {
          Effect   = "Allow"
          Action   = ["s3:ListBucket"]
          Resource = [aws_s3_bucket.artifacts.arn]
        },
        {
          Effect   = "Allow"
          Action   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey"]
          Resource = [aws_kms_key.artifacts.arn]
        }
    ])
  })
}

resource "aws_ecs_cluster" "main" {
  name = local.name
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_lb" "main" {
  name                       = substr(local.name, 0, 32)
  internal                   = false
  load_balancer_type         = "application"
  security_groups            = [aws_security_group.alb.id]
  subnets                    = aws_subnet.public[*].id
  drop_invalid_header_fields = true
  enable_deletion_protection = local.production
  idle_timeout               = 65
}

resource "aws_lb_target_group" "web" {
  name        = substr("${local.name}-web", 0, 32)
  port        = 3000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.main.id
  health_check {
    path     = "/"
    matcher  = "200-399"
    interval = 30
    timeout  = 5
  }
  deregistration_delay = 30
}

resource "aws_lb_target_group" "api" {
  name        = substr("${local.name}-api", 0, 32)
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.main.id
  health_check {
    path     = "/ready"
    matcher  = "200"
    interval = 30
    timeout  = 5
  }
  deregistration_delay = 30
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = local.custom_domain ? "redirect" : "forward"
    target_group_arn = local.custom_domain ? null : aws_lb_target_group.web.arn
    dynamic "redirect" {
      for_each = local.custom_domain ? [1] : []
      content {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }
  }
}

resource "aws_lb_listener" "https" {
  count             = local.custom_domain ? 1 : 0
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.alb_certificate_arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}

resource "aws_lb_listener_rule" "api_host" {
  listener_arn = local.custom_domain ? aws_lb_listener.https[0].arn : aws_lb_listener.http.arn
  priority     = 10
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
  condition {
    http_header {
      http_header_name = "X-Ambrosia-Origin"
      values           = ["api"]
    }
  }
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn
  container_definitions = jsonencode([{
    name         = "api"
    image        = var.api_image != "" ? var.api_image : "${aws_ecr_repository.api.repository_url}:bootstrap"
    essential    = true
    portMappings = [{ containerPort = 8000, hostPort = 8000, protocol = "tcp" }]
    environment = [
      { name = "ENVIRONMENT", value = var.environment },
      { name = "REQUIRE_DATABASE", value = "true" },
      { name = "ALLOW_INSECURE_DEV_IDENTITY", value = "false" },
      { name = "AUTH_EMAIL_MODE", value = local.custom_domain ? "ses" : "console" },
      { name = "AUTH_ALLOW_STAGING_CONSOLE_DELIVERY", value = !local.custom_domain && var.environment == "staging" ? "true" : "false" },
      { name = "AUTH_EXPOSE_DEVELOPMENT_TOKENS", value = !local.custom_domain && var.environment == "staging" ? "true" : "false" },
      { name = "AUTH_EMAIL_FROM", value = local.custom_domain ? "no-reply@${var.domain_name}" : "" },
      { name = "AUTH_SES_CONFIGURATION_SET", value = local.custom_domain ? aws_sesv2_configuration_set.transactional.configuration_set_name : "" },
      { name = "PUBLIC_WEB_URL", value = local.public_web_url },
      { name = "ALLOWED_ORIGINS", value = join(",", concat([local.public_web_url], var.extra_allowed_origins)) },
      { name = "AWS_REGION", value = var.aws_region },
      { name = "MARKET_SCANNER_ENABLED", value = "true" },
      { name = "MARKET_INTELLIGENCE_ENABLED", value = "false" },
      { name = "MARKET_SCANNER_PROMOTION_ENABLED", value = "false" },
      { name = "ALPHA_LAB_READ_ENABLED", value = "false" },
      { name = "ALPHA_LAB_WRITES_ENABLED", value = "false" },
      { name = "ALPHA_LAB_DEMO_SEED_ENABLED", value = "false" },
      { name = "SIGNALS_LAB_READ_ENABLED", value = "false" },
      { name = "SIGNALS_LAB_WRITES_ENABLED", value = "false" },
      { name = "SIGNALS_VALIDATION_ENABLED", value = "false" },
      { name = "SIGNALS_EXECUTION_HANDOFF_ENABLED", value = "false" },
      { name = "REPORT_EXPORT_ENABLED", value = "false" },
      { name = "SELECTIVE_INTEGRATION_ENABLED", value = "true" },
      { name = "SELECTIVE_INTEGRATION_ENFORCED", value = "true" },
      { name = "ARTIFACT_BUCKET", value = aws_s3_bucket.artifacts.id },
      { name = "ARTIFACT_KMS_KEY_ARN", value = aws_kms_key.artifacts.arn },
    ]
    secrets = [
      { name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.database_url.arn },
      { name = "REDIS_URL", valueFrom = aws_secretsmanager_secret.redis_url.arn },
      { name = "AUTH_TOKEN_PEPPER", valueFrom = aws_secretsmanager_secret.token_pepper.arn },
    ]
    readonlyRootFilesystem = true
    linuxParameters        = { initProcessEnabled = true }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.api.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "api"
      }
    }
  }])
}

resource "aws_ecs_task_definition" "web" {
  family                   = "${local.name}-web"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn
  container_definitions = jsonencode([{
    name                   = "web"
    image                  = var.web_image != "" ? var.web_image : "${aws_ecr_repository.web.repository_url}:bootstrap"
    essential              = true
    portMappings           = [{ containerPort = 3000, hostPort = 3000, protocol = "tcp" }]
    environment = [
      { name = "PORT", value = "3000" },
      { name = "NEXT_PUBLIC_ENABLE_LABS", value = "false" },
      { name = "NEXT_PUBLIC_ENABLE_MARKET_INTELLIGENCE", value = "false" },
      { name = "NEXT_PUBLIC_ENABLE_MARKET_SCANNER_PROMOTION", value = "false" },
      { name = "NEXT_PUBLIC_ENABLE_CALIBRATION_DEMO", value = "false" },
      { name = "NEXT_PUBLIC_ENABLE_REVIEW_EXPORT", value = "false" },
      { name = "NEXT_PUBLIC_ENABLE_ALPHA_LAB", value = "false" },
      { name = "NEXT_PUBLIC_ENABLE_SIGNALS_LAB", value = "false" },
    ]
    readonlyRootFilesystem = true
    linuxParameters        = { initProcessEnabled = true }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.web.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "web"
      }
    }
  }])
}

resource "aws_ecs_task_definition" "migration" {
  family                   = "${local.name}-migration"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn
  container_definitions = jsonencode([{
    name      = "migration"
    image     = var.api_image != "" ? var.api_image : "${aws_ecr_repository.api.repository_url}:bootstrap"
    essential = true
    command   = ["python", "/app/scripts/migrate_database.py", "--bootstrap-if-empty"]
    environment = [
      { name = "ENVIRONMENT", value = var.environment },
      { name = "RUNTIME_DATABASE_USER", value = "ambrosia_app" },
    ]
    secrets = [
      { name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.database_admin_url.arn },
      { name = "RUNTIME_DATABASE_PASSWORD", valueFrom = aws_secretsmanager_secret.database_runtime_password.arn },
    ]
    readonlyRootFilesystem = true
    linuxParameters        = { initProcessEnabled = true }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.api.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "migration"
      }
    }
  }])
}

resource "aws_ecs_service" "api" {
  name                               = "api"
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.api.arn
  desired_count                      = var.enable_services ? var.api_desired_count : 0
  launch_type                        = "FARGATE"
  platform_version                   = "LATEST"
  health_check_grace_period_seconds  = 90
  enable_execute_command             = true
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  network_configuration {
    subnets          = aws_subnet.application[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }
  depends_on = [aws_lb_listener_rule.api_host]
}

resource "aws_ecs_service" "web" {
  name                               = "web"
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.web.arn
  desired_count                      = var.enable_services ? var.web_desired_count : 0
  launch_type                        = "FARGATE"
  platform_version                   = "LATEST"
  health_check_grace_period_seconds  = 90
  enable_execute_command             = true
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  network_configuration {
    subnets          = aws_subnet.application[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.web.arn
    container_name   = "web"
    container_port   = 3000
  }
  depends_on = [aws_lb_listener.http, aws_lb_listener.https]
}

resource "aws_appautoscaling_target" "api" {
  count              = var.enable_services ? 1 : 0
  max_capacity       = 8
  min_capacity       = local.production ? 2 : 1
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "api_cpu" {
  count              = var.enable_services ? 1 : 0
  name               = "api-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api[0].resource_id
  scalable_dimension = aws_appautoscaling_target.api[0].scalable_dimension
  service_namespace  = aws_appautoscaling_target.api[0].service_namespace
  target_tracking_scaling_policy_configuration {
    target_value       = 55
    scale_in_cooldown  = 120
    scale_out_cooldown = 60
    predefined_metric_specification { predefined_metric_type = "ECSServiceAverageCPUUtilization" }
  }
}

resource "aws_cloudfront_function" "strip_api_prefix" {
  name    = "${local.name}-strip-api-prefix"
  runtime = "cloudfront-js-2.0"
  comment = "Route same-origin /api requests to FastAPI root paths"
  publish = true
  code    = <<-JAVASCRIPT
    function handler(event) {
      var request = event.request;
      if (request.uri === '/api') {
        request.uri = '/';
      } else if (request.uri.indexOf('/api/') === 0) {
        request.uri = request.uri.substring(4);
      }
      return request;
    }
  JAVASCRIPT
}

resource "aws_wafv2_web_acl" "regional" {
  name  = "${local.name}-regional"
  scope = "REGIONAL"
  default_action {
    allow {}
  }
  rule {
    name     = "auth-rate-limit"
    priority = 1
    action {
      block {}
    }
    statement {
      rate_based_statement {
        limit              = 100
        aggregate_key_type = "IP"
        scope_down_statement {
          or_statement {
            statement {
              byte_match_statement {
                search_string         = "/auth/"
                positional_constraint = "STARTS_WITH"
                field_to_match {
                  uri_path {}
                }
                text_transformation {
                  priority = 0
                  type     = "NONE"
                }
              }
            }
            statement {
              byte_match_statement {
                search_string         = "/api/auth/"
                positional_constraint = "STARTS_WITH"
                field_to_match {
                  uri_path {}
                }
                text_transformation {
                  priority = 0
                  type     = "NONE"
                }
              }
            }
          }
        }
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "auth-rate"
      sampled_requests_enabled   = true
    }
  }
  rule {
    name     = "expensive-workflow-rate-limit"
    priority = 2
    action {
      block {}
    }
    statement {
      rate_based_statement {
        limit              = 300
        aggregate_key_type = "IP"
        scope_down_statement {
          regex_match_statement {
            regex_string = "^/(api/)?(scanner|discovery|agents|llm/jobs)(/|$)"
            field_to_match {
              uri_path {}
            }
            text_transformation {
              priority = 0
              type     = "NONE"
            }
          }
        }
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "expensive-workflow-rate"
      sampled_requests_enabled   = true
    }
  }
  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = local.name
    sampled_requests_enabled   = true
  }
}

resource "aws_wafv2_web_acl_association" "alb" {
  resource_arn = aws_lb.main.arn
  web_acl_arn  = aws_wafv2_web_acl.regional.arn
}

resource "aws_wafv2_web_acl" "edge" {
  provider = aws.us_east_1
  name     = "${local.name}-edge"
  scope    = "CLOUDFRONT"
  default_action {
    allow {}
  }
  rule {
    name     = "aws-common"
    priority = 1
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "aws-common"
      sampled_requests_enabled   = true
    }
  }
  rule {
    name     = "edge-rate-limit"
    priority = 2
    action {
      block {}
    }
    statement {
      rate_based_statement {
        limit              = 2000
        aggregate_key_type = "IP"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "edge-rate"
      sampled_requests_enabled   = true
    }
  }
  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${local.name}-edge"
    sampled_requests_enabled   = true
  }
}

resource "aws_cloudfront_distribution" "web" {
  enabled         = true
  is_ipv6_enabled = true
  aliases         = local.custom_domain ? [local.configured_web_hostname] : []
  web_acl_id      = aws_wafv2_web_acl.edge.arn
  origin {
    domain_name = local.custom_domain ? local.origin_hostname : aws_lb.main.dns_name
    origin_id   = "alb-web"
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = local.custom_domain ? "https-only" : "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }
  origin {
    domain_name = local.custom_domain ? local.api_hostname : aws_lb.main.dns_name
    origin_id   = "alb-api"
    custom_header {
      name  = "X-Ambrosia-Origin"
      value = "api"
    }
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = local.custom_domain ? "https-only" : "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }
  ordered_cache_behavior {
    path_pattern             = "/api/*"
    target_origin_id         = "alb-api"
    viewer_protocol_policy   = "redirect-to-https"
    allowed_methods          = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods           = ["GET", "HEAD"]
    cache_policy_id          = data.aws_cloudfront_cache_policy.disabled.id
    origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_except_host.id
    compress                 = true
    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.strip_api_prefix.arn
    }
  }
  default_cache_behavior {
    target_origin_id         = "alb-web"
    viewer_protocol_policy   = "redirect-to-https"
    allowed_methods          = ["GET", "HEAD", "OPTIONS"]
    cached_methods           = ["GET", "HEAD"]
    cache_policy_id          = data.aws_cloudfront_cache_policy.disabled.id
    origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_except_host.id
    compress                 = true
  }
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
  viewer_certificate {
    cloudfront_default_certificate = !local.custom_domain
    acm_certificate_arn            = local.custom_domain ? var.cloudfront_certificate_arn : null
    ssl_support_method             = local.custom_domain ? "sni-only" : null
    minimum_protocol_version       = local.custom_domain ? "TLSv1.2_2021" : null
  }
  lifecycle {
    precondition {
      condition     = local.custom_domain || var.environment == "staging"
      error_message = "The generated CloudFront hostname is permitted only for staging."
    }
    precondition {
      condition = !local.custom_domain || alltrue([
        var.domain_name != "",
        var.hosted_zone_id != "",
        var.alb_certificate_arn != "",
        var.cloudfront_certificate_arn != "",
      ])
      error_message = "Custom-domain deployments require the domain, hosted zone, and both ACM certificate ARNs."
    }
  }
}

resource "aws_route53_record" "web" {
  count   = local.custom_domain ? 1 : 0
  zone_id = var.hosted_zone_id
  name    = local.configured_web_hostname
  type    = "A"
  alias {
    name                   = aws_cloudfront_distribution.web.domain_name
    zone_id                = aws_cloudfront_distribution.web.hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "api" {
  count   = local.custom_domain ? 1 : 0
  zone_id = var.hosted_zone_id
  name    = local.api_hostname
  type    = "A"
  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

resource "aws_route53_record" "origin" {
  count   = local.custom_domain ? 1 : 0
  zone_id = var.hosted_zone_id
  name    = local.origin_hostname
  type    = "A"
  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

resource "aws_sns_topic" "alarms" {
  name = "${local.name}-alarms"
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alert_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_sns_topic_subscription" "ses_email" {
  count     = var.alert_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.ses_events.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${local.name}-api-5xx"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 5
  treat_missing_data  = "notBreaching"
  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
    TargetGroup  = aws_lb_target_group.api.arn_suffix
  }
  alarm_actions = [aws_sns_topic.alarms.arn]
}

resource "aws_cloudwatch_metric_alarm" "database_cpu" {
  alarm_name          = "${local.name}-database-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  dimensions          = { DBInstanceIdentifier = aws_db_instance.postgres.id }
  alarm_actions       = [aws_sns_topic.alarms.arn]
}
