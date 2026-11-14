#!/usr/bin/env python3
"""
Load test: invokes the Fetcher Lambda concurrently and reports latency/
throughput. Not a replacement for a proper tool (k6/Locust) but enough to
generate real CloudWatch data for the dashboard and cost report.

Usage:
    python scripts/load_test.py --function pipelinewatch-fetcher --concurrency 10 --rounds 5
"""
import argparse
import concurrent.futures
import json
import time

import boto3


def invoke_once(client, function_name):
    start = time.perf_counter()
    resp = client.invoke(FunctionName=function_name, InvocationType="RequestResponse")
    duration_ms = (time.perf_counter() - start) * 1000
    payload = json.loads(resp["Payload"].read())
    return duration_ms, resp["StatusCode"], payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--function", required=True, help="Lambda function name")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args()

    client = boto3.client("lambda", region_name=args.region)
    all_durations = []
    errors = 0

    for round_num in range(1, args.rounds + 1):
        print(f"Round {round_num}/{args.rounds} - firing {args.concurrency} concurrent invocations")
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = [
                pool.submit(invoke_once, client, args.function)
                for _ in range(args.concurrency)
            ]
            for future in concurrent.futures.as_completed(futures):
                try:
                    duration_ms, status_code, payload = future.result()
                    all_durations.append(duration_ms)
                    if status_code != 200 or payload.get("failed"):
                        errors += 1
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    print(f"  invocation error: {exc}")
        time.sleep(1)

    if all_durations:
        all_durations.sort()
        p50 = all_durations[len(all_durations) // 2]
        p99 = all_durations[int(len(all_durations) * 0.99) - 1]
        print("\n--- Results ---")
        print(f"Total invocations: {len(all_durations) + errors}")
        print(f"Errors:            {errors}")
        print(f"p50 latency:       {p50:.0f} ms")
        print(f"p99 latency:       {p99:.0f} ms")
        print(f"min / max:         {min(all_durations):.0f} ms / {max(all_durations):.0f} ms")
        print("\nPull the corresponding Duration/Invocations/Errors metrics from")
        print("the CloudWatch dashboard for this window to cross-check these numbers")
        print("and feed the cost report.")


if __name__ == "__main__":
    main()
