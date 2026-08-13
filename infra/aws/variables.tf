variable "project" {
  type    = string
  default = "ambrosia"
}

variable "owner" {
  type        = string
  description = "Named operational owner applied to every AWS resource that supports tags"
  validation {
    condition     = length(trimspace(var.owner)) >= 2
    error_message = "owner must name the accountable staging operator or team."
  }
}

variable "cost_center" {
  type        = string
  description = "Approved cost-allocation identifier"
  validation {
    condition     = length(trimspace(var.cost_center)) >= 2
    error_message = "cost_center must be an approved non-empty allocation identifier."
  }
}

variable "data_classification" {
  type        = string
  default     = "synthetic"
  description = "Data classification for this environment"
  validation {
    condition     = contains(["synthetic", "approved-staging", "approved-production"], var.data_classification)
    error_message = "data_classification must be synthetic, approved-staging, or approved-production."
  }
}

variable "environment" {
  type = string
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production"
  }
}

variable "ollama_review_bridge_organization_ids" {
  type        = list(string)
  default     = []
  description = "Tenant UUID canary allowlist for outbound Ollama review operations"
  validation {
    condition     = alltrue([for id in var.ollama_review_bridge_organization_ids : can(regex("^[0-9a-fA-F-]{36}$", id))])
    error_message = "Every Ollama bridge organization identifier must be a UUID."
  }
}

variable "ollama_default_model_digest" {
  type        = string
  default     = ""
  description = "Immutable approved Ollama digest selected when the browser does not specify a model"
}

variable "ollama_approved_model_digests" {
  type        = list(string)
  default     = []
  description = "Immutable Ollama model digests allowed for staging worker execution"
}

variable "aws_region" {
  type    = string
  default = "ca-central-1"
  validation {
    condition     = var.aws_region == "ca-central-1"
    error_message = "The Index133 staging control plane is restricted to ca-central-1."
  }
}

variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
}

variable "custom_domain_enabled" {
  type        = bool
  default     = true
  description = "Use Route53 and ACM hostnames; staging may disable this to use the generated CloudFront HTTPS hostname"
}

variable "domain_name" {
  type        = string
  default     = ""
  description = "Route53-managed apex domain, for example ambrosia.example"
  validation {
    condition     = var.domain_name == "" || (can(regex("^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$", var.domain_name)) && var.domain_name != "example.com")
    error_message = "domain_name must be empty for generated-hostname staging, or a real lower-case DNS apex other than example.com."
  }
}

variable "auth_email_from" {
  type        = string
  default     = ""
  description = "Verified SES sender address used when staging runs on a generated CloudFront hostname"
  validation {
    condition     = var.auth_email_from == "" || can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.auth_email_from))
    error_message = "auth_email_from must be empty or a valid email address."
  }
}

variable "auth_ses_identity_arn" {
  type        = string
  default     = ""
  description = "Verified ca-central-1 SES email or domain identity authorized to send auth email"
  validation {
    condition     = var.auth_ses_identity_arn == "" || can(regex("^arn:aws[a-z-]*:ses:ca-central-1:[0-9]{12}:identity/.+", var.auth_ses_identity_arn))
    error_message = "auth_ses_identity_arn must be empty or a ca-central-1 SES identity ARN."
  }
}

variable "hosted_zone_id" {
  type        = string
  default     = ""
  description = "Route53 public hosted zone id for domain_name"
  validation {
    condition     = var.hosted_zone_id == "" || can(regex("^Z[A-Z0-9]+$", var.hosted_zone_id))
    error_message = "hosted_zone_id must be empty for generated-hostname staging, or a Route53 identifier beginning with Z."
  }
}

variable "alb_certificate_arn" {
  type        = string
  default     = ""
  description = "Regional ACM certificate covering the API and CloudFront-to-ALB origin hostnames"
  validation {
    condition     = var.alb_certificate_arn == "" || can(regex("^arn:aws[a-z-]*:acm:ca-central-1:[0-9]{12}:certificate/", var.alb_certificate_arn))
    error_message = "alb_certificate_arn must be empty for generated-hostname staging, or identify a ca-central-1 ACM certificate."
  }
}

variable "cloudfront_certificate_arn" {
  type        = string
  default     = ""
  description = "us-east-1 ACM certificate covering the web hostname"
  validation {
    condition     = var.cloudfront_certificate_arn == "" || can(regex("^arn:aws[a-z-]*:acm:us-east-1:[0-9]{12}:certificate/", var.cloudfront_certificate_arn))
    error_message = "cloudfront_certificate_arn must be empty for generated-hostname staging, or identify a us-east-1 ACM certificate."
  }
}

variable "api_image" {
  type        = string
  default     = ""
  description = "Immutable ECR API image reference, preferably by sha256 digest"
  validation {
    condition     = var.api_image == "" || can(regex("@sha256:[0-9a-f]{64}$", var.api_image))
    error_message = "api_image must be empty during registry bootstrap or be an immutable sha256 digest reference."
  }
}

variable "web_image" {
  type        = string
  default     = ""
  description = "Immutable ECR web image reference, preferably by sha256 digest"
  validation {
    condition     = var.web_image == "" || can(regex("@sha256:[0-9a-f]{64}$", var.web_image))
    error_message = "web_image must be empty during registry bootstrap or be an immutable sha256 digest reference."
  }
}

variable "api_desired_count" {
  type    = number
  default = 2
  validation {
    condition     = var.api_desired_count >= 1 && var.api_desired_count <= 8 && floor(var.api_desired_count) == var.api_desired_count
    error_message = "api_desired_count must be an integer from 1 through 8."
  }
}

variable "web_desired_count" {
  type    = number
  default = 2
  validation {
    condition     = var.web_desired_count >= 1 && var.web_desired_count <= 8 && floor(var.web_desired_count) == var.web_desired_count
    error_message = "web_desired_count must be an integer from 1 through 8."
  }
}

variable "enable_services" {
  type        = bool
  default     = true
  description = "Set false for the first infrastructure apply, run the migration task, then enable"
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.small"
}

variable "redis_node_type" {
  type    = string
  default = "cache.t4g.small"
}

variable "alert_email" {
  type        = string
  default     = ""
  description = "Optional operations email subscribed to the alarm topic"
}

variable "extra_allowed_origins" {
  type    = list(string)
  default = []
}
