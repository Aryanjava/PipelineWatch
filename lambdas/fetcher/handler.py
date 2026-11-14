"""
Fetcher Lambda.

Triggered on a schedule by EventBridge. Calls the OpenWeatherMap API for
each configured city and writes the raw JSON response to S3 under
raw/{city}/{timestamp}.json.

Writing raw data first (rather than transforming inline) means we always
have an unmodified copy of what the API actually returned - useful for
replaying/debugging if the transform logic has a bug later.
"""
import json
import os
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone

import boto3

s3 = boto3.client("s3")

RAW_BUCKET = os.environ["RAW_BUCKET"]
CITIES = [c.strip() for c in os.environ["CITIES"].split(",") if c.strip()]
API_KEY = os.environ["OPENWEATHER_API_KEY"]
API_URL = "https://api.openweathermap.org/data/2.5/weather"


def fetch_city(city: str) -> dict:
    params = f"?q={urllib.parse.quote(city)}&appid={API_KEY}&units=metric"
    req = urllib.request.Request(API_URL + params)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def lambda_handler(event, context):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results = {"succeeded": [], "failed": []}

    for city in CITIES:
        try:
            data = fetch_city(city)
            key = f"raw/{city.replace(' ', '_').lower()}/{timestamp}.json"
            s3.put_object(
                Bucket=RAW_BUCKET,
                Key=key,
                Body=json.dumps(data).encode("utf-8"),
                ContentType="application/json",
            )
            results["succeeded"].append({"city": city, "key": key})
        except Exception as exc:  # noqa: BLE001 - deliberately broad: any per-city
            # failure (network, bad JSON, malformed response) should be
            # captured and reported, not crash the whole batch.
            # Let this bubble up if EVERY city fails - a single-city failure
            # (e.g. bad city name) shouldn't kill the whole batch, but if the
            # API key itself is invalid every call will fail and we want the
            # Lambda to raise so it lands on the DLQ and fires an alert.
            results["failed"].append({"city": city, "error": str(exc)})

    if results["failed"] and not results["succeeded"]:
        raise RuntimeError(f"All fetches failed: {results['failed']}")

    return results
