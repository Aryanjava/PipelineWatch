#!/usr/bin/env python3
"""
Pulls average Lambda duration + invocation count from CloudWatch for a given
window and computes an estimated cost per 1,000 invocations at the
function's current memory size, using published AWS Lambda pricing.

This is what turns "I optimized cost" from a claim into a number for the
README's cost table.

Usage:
    python scripts/cost_report.py --function pipelinewatch-transform \
        --memory-mb 256 --hours 6
"""
import argparse
from datetime import datetime, timedelta, timezone

import boto3

# us-east-1 on-demand pricing as of early 2026 - update if pricing changes,
# or better: pull live from the AWS Price List API for a more rigorous report.
PRICE_PER_GB_SECOND = 0.0000166667
PRICE_PER_REQUEST = 0.0000002


def get_metric_stat(client, function_name, metric_name, stat, start, end):
    resp = client.get_metric_statistics(
        Namespace="AWS/Lambda",
        MetricName=metric_name,
        Dimensions=[{"Name": "FunctionName", "Value": function_name}],
        StartTime=start,
        EndTime=end,
        Period=3600,
        Statistics=[stat],
    )
    points = resp.get("Datapoints", [])
    if not points:
        return None
    return points


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--function", required=True)
    parser.add_argument("--memory-mb", type=int, required=True)
    parser.add_argument("--hours", type=int, default=6, help="Lookback window")
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args()

    client = boto3.client("cloudwatch", region_name=args.region)
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=args.hours)

    duration_points = get_metric_stat(client, args.function, "Duration", "Average", start, end)
    invocation_points = get_metric_stat(client, args.function, "Invocations", "Sum", start, end)

    if not duration_points or not invocation_points:
        print("No data found for this window - has the function been invoked recently?")
        return

    avg_duration_ms = sum(p["Average"] for p in duration_points) / len(duration_points)
    total_invocations = sum(p["Sum"] for p in invocation_points)

    gb_seconds_per_invocation = (args.memory_mb / 1024) * (avg_duration_ms / 1000)
    compute_cost_per_invocation = gb_seconds_per_invocation * PRICE_PER_GB_SECOND
    total_cost_per_invocation = compute_cost_per_invocation + PRICE_PER_REQUEST
    cost_per_1000 = total_cost_per_invocation * 1000

    print(f"Function:              {args.function}")
    print(f"Memory:                {args.memory_mb} MB")
    print(f"Window:                last {args.hours}h")
    print(f"Total invocations:     {total_invocations:.0f}")
    print(f"Avg duration:          {avg_duration_ms:.1f} ms")
    print(f"Est. cost per 1,000:   ${cost_per_1000:.6f}")
    print("\nCopy this row into README.md's cost optimization table, then")
    print("re-run after changing lambda_memory_mb in terraform.tfvars and")
    print("redeploying, to get the comparison row.")


if __name__ == "__main__":
    main()
