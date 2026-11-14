"""
Slack forwarder Lambda.

SNS has no native Slack integration, so this small Lambda subscribes to the
alerts topic and posts each message to a Slack incoming webhook. Kept
deliberately tiny and dependency-free (stdlib only) since its only job is
translating one message format into another.
"""
import json
import os
import urllib.request

SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]


def lambda_handler(event, context):
    for record in event.get("Records", []):
        sns_message = record["Sns"]["Message"]
        subject = record["Sns"].get("Subject", "PipelineWatch Alert")

        payload = {
            "text": f"*{subject}*\n{sns_message}"
        }
        req = urllib.request.Request(
            SLACK_WEBHOOK_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status >= 300:
                raise RuntimeError(f"Slack webhook returned status {resp.status}")

    return {"forwarded": len(event.get("Records", []))}
