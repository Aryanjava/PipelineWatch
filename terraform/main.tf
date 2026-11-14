resource "random_id" "suffix" {
  byte_length = 3
}

# --------------------------------------------------------------------------
# S3 - raw data landing zone
# --------------------------------------------------------------------------
resource "aws_s3_bucket" "raw_data" {
  bucket = "${var.project_name}-raw-${random_id.suffix.hex}"
}

resource "aws_s3_bucket_versioning" "raw_data" {
  bucket = aws_s3_bucket.raw_data.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_lifecycle_configuration" "raw_data" {
  bucket = aws_s3_bucket.raw_data.id
  rule {
    id     = "expire-raw-after-30-days"
    status = "Enabled"
    filter { prefix = "raw/" }
    expiration { days = 30 }
  }
}

resource "aws_s3_bucket_public_access_block" "raw_data" {
  bucket                  = aws_s3_bucket.raw_data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Required so S3 object-created events can be routed to EventBridge, which
# triggers the Step Functions workflow below.
resource "aws_s3_bucket_notification" "raw_data_eventbridge" {
  bucket      = aws_s3_bucket.raw_data.id
  eventbridge = true
}

# --------------------------------------------------------------------------
# DynamoDB - processed data store
# --------------------------------------------------------------------------
resource "aws_dynamodb_table" "processed_data" {
  name         = "${var.project_name}-processed-data"
  billing_mode = "PAY_PER_REQUEST" # on-demand: no capacity planning needed at this scale, see README cost notes
  hash_key     = "city"
  range_key    = "timestamp"

  attribute {
    name = "city"
    type = "S"
  }
  attribute {
    name = "timestamp"
    type = "S"
  }
}

# --------------------------------------------------------------------------
# SQS - dead letter queue for the fetcher Lambda (async invoke failures)
# --------------------------------------------------------------------------
resource "aws_sqs_queue" "dlq" {
  name                      = "${var.project_name}-dlq"
  message_retention_seconds = 1209600 # 14 days
}

resource "aws_cloudwatch_metric_alarm" "dlq_not_empty" {
  alarm_name          = "${var.project_name}-dlq-not-empty"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Fires when the fetcher DLQ receives a failed event"
  dimensions          = { QueueName = aws_sqs_queue.dlq.name }
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"
}

# --------------------------------------------------------------------------
# SNS - alert topic (anomalies + pipeline failures)
# --------------------------------------------------------------------------
resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# --------------------------------------------------------------------------
# Lambdas - all built from the shared modules/lambda_function module
# --------------------------------------------------------------------------
module "fetcher" {
  source          = "./modules/lambda_function"
  function_name   = "${var.project_name}-fetcher"
  source_dir      = "${path.module}/../lambdas/fetcher"
  role_arn        = aws_iam_role.fetcher.arn
  timeout         = 30
  memory_size     = 128
  dead_letter_arn = aws_sqs_queue.dlq.arn
  enable_tracing  = true

  environment_variables = {
    RAW_BUCKET          = aws_s3_bucket.raw_data.bucket
    CITIES              = var.cities
    OPENWEATHER_API_KEY = var.openweather_api_key
  }
}

module "transform" {
  source         = "./modules/lambda_function"
  function_name  = "${var.project_name}-transform"
  source_dir     = "${path.module}/../lambdas/transform"
  role_arn       = aws_iam_role.transform.arn
  timeout        = 15
  memory_size    = var.lambda_memory_mb
  enable_tracing = true

  environment_variables = {
    TABLE_NAME           = aws_dynamodb_table.processed_data.name
    ANOMALY_TEMP_CELSIUS = tostring(var.anomaly_temp_celsius)
  }
}

# Forwards SNS alerts to Slack (SNS has no native Slack integration, so a
# thin Lambda bridges the two).
module "slack_forwarder" {
  count          = var.slack_webhook_url != "" ? 1 : 0
  source         = "./modules/lambda_function"
  function_name  = "${var.project_name}-slack-forwarder"
  source_dir     = "${path.module}/../lambdas/slack_forwarder"
  role_arn       = aws_iam_role.slack_forwarder[0].arn
  timeout        = 10
  memory_size    = 128
  enable_tracing = false

  environment_variables = {
    SLACK_WEBHOOK_URL = var.slack_webhook_url
  }
}

resource "aws_lambda_permission" "allow_sns_invoke_slack" {
  count         = var.slack_webhook_url != "" ? 1 : 0
  statement_id  = "AllowSNSInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.slack_forwarder[0].function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.alerts.arn
}

resource "aws_sns_topic_subscription" "slack" {
  count     = var.slack_webhook_url != "" ? 1 : 0
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "lambda"
  endpoint  = module.slack_forwarder[0].arn
}

# --------------------------------------------------------------------------
# EventBridge - schedule that triggers the fetcher on a cadence
# --------------------------------------------------------------------------
resource "aws_cloudwatch_event_rule" "schedule" {
  name                = "${var.project_name}-fetch-schedule"
  schedule_expression = var.fetch_schedule_expression
}

resource "aws_cloudwatch_event_target" "schedule_target" {
  rule = aws_cloudwatch_event_rule.schedule.name
  arn  = module.fetcher.arn
}

resource "aws_lambda_permission" "allow_eventbridge_schedule" {
  statement_id  = "AllowEventBridgeSchedule"
  action        = "lambda:InvokeFunction"
  function_name = module.fetcher.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.schedule.arn
}

# --------------------------------------------------------------------------
# EventBridge - S3 object-created -> Step Functions execution
# --------------------------------------------------------------------------
resource "aws_cloudwatch_event_rule" "s3_object_created" {
  name = "${var.project_name}-s3-object-created"
  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["Object Created"]
    detail = {
      bucket = { name = [aws_s3_bucket.raw_data.bucket] }
      object = { key = [{ prefix = "raw/" }] }
    }
  })
}

resource "aws_cloudwatch_event_target" "start_pipeline" {
  rule     = aws_cloudwatch_event_rule.s3_object_created.name
  arn      = aws_sfn_state_machine.pipeline.arn
  role_arn = aws_iam_role.eventbridge_sfn.arn
}
