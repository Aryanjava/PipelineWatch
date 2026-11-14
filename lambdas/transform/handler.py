"""
Transform Lambda.

Invoked as the first state of the Step Functions workflow. The workflow is
started by an EventBridge rule matching S3 "Object Created" events, so the
incoming `event` is the raw EventBridge event envelope - the bucket/key we
need live at event["detail"]["bucket"]["name"] / event["detail"]["object"]["key"].

Responsibilities:
  1. Read the raw JSON the fetcher wrote to S3
  2. Validate + extract the fields we care about
  3. Write a normalized item to DynamoDB
  4. Decide whether this reading is an anomaly (temp above threshold)
  5. Return {"anomaly": bool, "message": str, ...} - the Step Functions
     Choice state branches on `anomaly` to decide whether to publish an SNS
     alert.

Any unhandled exception here is caught by the state machine's Catch block
and routed to a failure-notification state - so we deliberately do NOT
swallow errors, we let them raise.
"""
import json
import os
from datetime import datetime, timezone

import boto3

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

TABLE_NAME = os.environ["TABLE_NAME"]
ANOMALY_TEMP_CELSIUS = float(os.environ["ANOMALY_TEMP_CELSIUS"])

table = dynamodb.Table(TABLE_NAME)


def lambda_handler(event, context):
    bucket = event["detail"]["bucket"]["name"]
    key = event["detail"]["object"]["key"]

    obj = s3.get_object(Bucket=bucket, Key=key)
    raw = json.loads(obj["Body"].read())

    city = raw.get("name")
    temp = raw.get("main", {}).get("temp")
    humidity = raw.get("main", {}).get("humidity")

    if city is None or temp is None:
        raise ValueError(f"Malformed weather payload at s3://{bucket}/{key}")

    timestamp = datetime.now(timezone.utc).isoformat()

    table.put_item(
        Item={
            "city": city,
            "timestamp": timestamp,
            "temperature_c": str(temp),
            "humidity_pct": str(humidity) if humidity is not None else "unknown",
            "source_key": key,
        }
    )

    is_anomaly = temp >= ANOMALY_TEMP_CELSIUS
    message = (
        f"PipelineWatch anomaly: {city} reported {temp}C "
        f"(threshold {ANOMALY_TEMP_CELSIUS}C)"
        if is_anomaly
        else f"{city} processed normally at {temp}C"
    )

    return {
        "anomaly": is_anomaly,
        "message": message,
        "city": city,
        "temperature_c": temp,
    }
