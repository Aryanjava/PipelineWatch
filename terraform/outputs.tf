output "raw_bucket_name" {
  value = aws_s3_bucket.raw_data.bucket
}

output "dynamodb_table_name" {
  value = aws_dynamodb_table.processed_data.name
}

output "sns_topic_arn" {
  value = aws_sns_topic.alerts.arn
}

output "state_machine_arn" {
  value = aws_sfn_state_machine.pipeline.arn
}

output "dashboard_url" {
  value = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.main.dashboard_name}"
}

output "fetcher_lambda_name" {
  value = module.fetcher.function_name
}

output "transform_lambda_name" {
  value = module.transform.function_name
}
