import json
import os
from unittest.mock import patch, MagicMock

import boto3
import pytest
from moto import mock_aws

os.environ.setdefault("RAW_BUCKET", "test-raw-bucket")
os.environ.setdefault("CITIES", "London,Tokyo")
os.environ.setdefault("OPENWEATHER_API_KEY", "fake-key")

from lambdas.fetcher import handler  # noqa: E402


FAKE_RESPONSE = json.dumps(
    {"name": "London", "main": {"temp": 18.5, "humidity": 60}}
).encode()


@mock_aws
def test_fetch_writes_raw_json_to_s3():
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-raw-bucket")

    fake_urlopen = MagicMock()
    fake_urlopen.__enter__.return_value.read.return_value = FAKE_RESPONSE

    with patch("lambdas.fetcher.handler.urllib.request.urlopen", return_value=fake_urlopen):
        result = handler.lambda_handler({}, None)

    assert len(result["succeeded"]) == 2
    assert result["failed"] == []

    objects = s3.list_objects_v2(Bucket="test-raw-bucket")["Contents"]
    assert len(objects) == 2
    assert all(o["Key"].startswith("raw/") for o in objects)


@mock_aws
def test_all_cities_failing_raises():
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-raw-bucket")

    with patch(
        "lambdas.fetcher.handler.urllib.request.urlopen",
        side_effect=Exception("boom"),
    ):
        with pytest.raises(Exception):
            handler.lambda_handler({}, None)
