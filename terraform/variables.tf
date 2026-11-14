variable "project_name" {
  description = "Project name, used as a prefix for all resources"
  type        = string
  default     = "pipelinewatch"
}

variable "environment" {
  description = "Deployment environment (dev/prod)"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "ap-south-1"
}

variable "cities" {
  description = "Comma-separated list of cities to fetch weather for"
  type        = string
  default     = "London,New York,Bengaluru,Tokyo,Delhi"
}

variable "openweather_api_key" {
  description = "OpenWeatherMap API key (pass via TF_VAR_openweather_api_key or a .tfvars file that is gitignored)"
  type        = string
  sensitive   = true
}

variable "anomaly_temp_celsius" {
  description = "Temperature threshold (C) above which we flag an anomaly"
  type        = number
  default     = 40
}

variable "fetch_schedule_expression" {
  description = "EventBridge schedule for the fetcher Lambda"
  type        = string
  default     = "rate(15 minutes)"
}

variable "slack_webhook_url" {
  description = "Slack incoming webhook URL for alerts (optional - leave blank to skip Slack wiring)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "alert_email" {
  description = "Email address to subscribe to the SNS alert topic"
  type        = string
  default     = "aryan04102000@yahoo.com"
}

variable "lambda_memory_mb" {
  description = "Memory (MB) for the transform Lambda - start at 512 (baseline), later lower to 256 for the cost comparison"
  type        = number
  default     = 256
}
