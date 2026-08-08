variable "project" {
  type    = string
  default = "ambrosia"
}

variable "environment" {
  type = string
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production"
  }
}

variable "aws_region" {
  type    = string
  default = "ca-central-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
}

variable "domain_name" {
  type        = string
  description = "Route53-managed apex domain, for example ambrosia.example"
}

variable "hosted_zone_id" {
  type        = string
  description = "Route53 public hosted zone id for domain_name"
}

variable "alb_certificate_arn" {
  type        = string
  description = "Regional ACM certificate covering the API and CloudFront-to-ALB origin hostnames"
}

variable "cloudfront_certificate_arn" {
  type        = string
  description = "us-east-1 ACM certificate covering the web hostname"
}

variable "api_image" {
  type        = string
  default     = ""
  description = "Immutable ECR API image reference, preferably by sha256 digest"
}

variable "web_image" {
  type        = string
  default     = ""
  description = "Immutable ECR web image reference, preferably by sha256 digest"
}

variable "api_desired_count" {
  type    = number
  default = 2
}

variable "web_desired_count" {
  type    = number
  default = 2
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
