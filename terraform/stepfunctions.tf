resource "aws_sfn_state_machine" "pipeline" {
  name     = "${var.project_name}-pipeline"
  role_arn = aws_iam_role.step_functions.arn

  tracing_configuration {
    enabled = true
  }

  definition = jsonencode({
    Comment = "PipelineWatch: transform raw event, flag anomalies, alert on failure"
    StartAt = "Transform"
    States = {
      Transform = {
        Type     = "Task"
        Resource = module.transform.arn
        Next     = "CheckAnomaly"
        Catch = [{
          ErrorEquals = ["States.ALL"]
          Next        = "PublishFailure"
          ResultPath  = "$.error"
        }]
      }
      CheckAnomaly = {
        Type = "Choice"
        Choices = [{
          Variable      = "$.anomaly"
          BooleanEquals = true
          Next          = "PublishAlert"
        }]
        Default = "Success"
      }
      PublishAlert = {
        Type     = "Task"
        Resource = "arn:aws:states:::sns:publish"
        Parameters = {
          TopicArn    = aws_sns_topic.alerts.arn
          "Message.$" = "$.message"
        }
        Next = "Success"
      }
      PublishFailure = {
        Type     = "Task"
        Resource = "arn:aws:states:::sns:publish"
        Parameters = {
          TopicArn = aws_sns_topic.alerts.arn
          Message  = "PipelineWatch: Transform step failed - check CloudWatch Logs for /aws/lambda/${var.project_name}-transform"
        }
        End = true
      }
      Success = { Type = "Succeed" }
    }
  })
}

# --------------------------------------------------------------------------
# CloudWatch dashboard - the observability artifact for the README/demo
# --------------------------------------------------------------------------
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project_name}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        x    = 0, y = 0, width = 12, height = 6
        properties = {
          title  = "Lambda Invocations & Errors"
          region = var.aws_region
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", module.fetcher.function_name],
            ["AWS/Lambda", "Errors", "FunctionName", module.fetcher.function_name],
            ["AWS/Lambda", "Invocations", "FunctionName", module.transform.function_name],
            ["AWS/Lambda", "Errors", "FunctionName", module.transform.function_name]
          ]
          stat = "Sum"
        }
      },
      {
        type = "metric"
        x    = 12, y = 0, width = 12, height = 6
        properties = {
          title   = "Transform Lambda Duration (ms)"
          region  = var.aws_region
          metrics = [["AWS/Lambda", "Duration", "FunctionName", module.transform.function_name]]
          stat    = "Average"
        }
      },
      {
        type = "metric"
        x    = 0, y = 6, width = 12, height = 6
        properties = {
          title  = "DynamoDB Consumed Capacity"
          region = var.aws_region
          metrics = [
            ["AWS/DynamoDB", "ConsumedWriteCapacityUnits", "TableName", aws_dynamodb_table.processed_data.name]
          ]
          stat = "Sum"
        }
      },
      {
        type = "metric"
        x    = 12, y = 6, width = 12, height = 6
        properties = {
          title   = "DLQ Depth (failed fetch events)"
          region  = var.aws_region
          metrics = [["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", aws_sqs_queue.dlq.name]]
          stat    = "Maximum"
        }
      }
    ]
  })
}
