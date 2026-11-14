variable "function_name" {
  type = string
}

variable "source_dir" {
  description = "Path to the directory containing handler.py"
  type        = string
}

variable "handler" {
  type    = string
  default = "handler.lambda_handler"
}

variable "runtime" {
  type    = string
  default = "python3.12"
}

variable "role_arn" {
  type = string
}

variable "timeout" {
  type    = number
  default = 15
}

variable "memory_size" {
  type    = number
  default = 128
}

variable "environment_variables" {
  type    = map(string)
  default = {}
}

variable "dead_letter_arn" {
  description = "Optional SQS/SNS ARN for async-invoke failures"
  type        = string
  default     = null
}

variable "enable_tracing" {
  description = "Enable AWS X-Ray active tracing"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  type    = number
  default = 14
}
