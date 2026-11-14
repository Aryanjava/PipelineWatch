#!/usr/bin/env python3
"""
Chaos test for PipelineWatch.

Serverless "chaos engineering" isn't about killing pods - it's about
proving the failure-detection path actually works. This script:

  1. Snapshots the fetcher Lambda's current environment variables
  2. Deliberately corrupts OPENWEATHER_API_KEY so every API call fails
  3. Invokes the function directly (bypassing the schedule, for speed)
  4. Polls the DLQ for the failed message and the CloudWatch alarm state
  5. Restores the original, valid configuration

Run this, then check Slack/email for the alert that should have fired, and
screenshot the DLQ message + alarm state transition for your README/demo.
That screenshot is your chaos-test evidence.

Usage:
    python scripts/chaos_test.py --function pipelinewatch-fetcher \
        --dlq-url https://sqs.us-east-1.amazonaws.com/.../pipelinewatch-dlq \
        --alarm-name pipelinewatch-dlq-not-empty
"""
import argparse
import time

import boto3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--function", required=True)
    parser.add_argument("--dlq-url", required=True)
    parser.add_argument("--alarm-name", required=True)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--poll-seconds", type=int, default=600)
    args = parser.parse_args()

    lambda_client = boto3.client("lambda", region_name=args.region)
    sqs = boto3.client("sqs", region_name=args.region)
    cloudwatch = boto3.client("cloudwatch", region_name=args.region)

    print("1. Snapshotting current fetcher configuration...")
    original_config = lambda_client.get_function_configuration(FunctionName=args.function)
    original_env = original_config["Environment"]["Variables"]

    print("2. Injecting a bad API key to force every fetch to fail...")
    broken_env = dict(original_env)
    broken_env["OPENWEATHER_API_KEY"] = "deliberately-invalid-for-chaos-test"
    lambda_client.update_function_configuration(
        FunctionName=args.function,
        Environment={"Variables": broken_env},
    )
    waiter = lambda_client.get_waiter("function_updated")
    waiter.wait(FunctionName=args.function)

    print("3. Invoking the fetcher asynchronously (mirrors the real EventBridge trigger)...")
    lambda_client.invoke(FunctionName=args.function, InvocationType="Event")

    print(f"4. Polling DLQ and alarm state for up to {args.poll_seconds}s...")
    deadline = time.time() + args.poll_seconds
    dlq_hit = False
    alarm_hit = False
    while time.time() < deadline and not (dlq_hit and alarm_hit):
        if not dlq_hit:
            attrs = sqs.get_queue_attributes(
                QueueUrl=args.dlq_url,
                AttributeNames=["ApproximateNumberOfMessages"],
            )["Attributes"]
            if int(attrs["ApproximateNumberOfMessages"]) > 0:
                dlq_hit = True
                print("   -> Message landed on the DLQ.")
        if not alarm_hit:
            alarm = cloudwatch.describe_alarms(AlarmNames=[args.alarm_name])["MetricAlarms"][0]
            if alarm["StateValue"] == "ALARM":
                alarm_hit = True
                print("   -> CloudWatch alarm transitioned to ALARM.")
        if not (dlq_hit and alarm_hit):
            time.sleep(5)

    print("\n5. Restoring original configuration...")
    lambda_client.update_function_configuration(
        FunctionName=args.function,
        Environment={"Variables": original_env},
    )
    waiter.wait(FunctionName=args.function)
    print("   Configuration restored.")

    print("\n--- Chaos test summary ---")
    print(f"DLQ received failed message: {dlq_hit}")
    print(f"CloudWatch alarm fired:      {alarm_hit}")
    if dlq_hit and alarm_hit:
        print("PASS: failure was detected and alerted end-to-end.")
    else:
        print("INCOMPLETE: one or more signals did not fire within the poll window - "
              "check timing/permissions before assuming a real gap.")


if __name__ == "__main__":
    main()
