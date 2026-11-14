import json
import os

import boto3
import pytest
from moto import mock_aws

os.environ.setdefault("TABLE_NAME", "test-processed-data")
os.environ.setdefault("ANOMALY_TEMP_CELSIUS", "40")

from lambdas.transform import handler  # noqa: E402


def _make_event(bucket, key):
    return {"detail": {"bucket": {"name": bucket}, "object": {"key": key}}}


@pytest.fixture
def aws_env():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-raw-bucket")

        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        ddb.create_table(
            TableName="test-processed-data",
            KeySchema=[
                {"AttributeName": "city", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "city", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield s3, ddb


def test_normal_reading_is_not_anomaly(aws_env):
    s3, ddb = aws_env
    s3.put_object(
        Bucket="test-raw-bucket",
        Key="raw/london/20260924T120000Z.json",
        Body=json.dumps({"name": "London", "main": {"temp": 18.5, "humidity": 60}}),
    )

    # handler module-level globals were bound before the mock table existed
    # in some test orders, so rebind to be safe
    handler.table = ddb.Table("test-processed-data")

    result = handler.lambda_handler(
        _make_event("test-raw-bucket", "raw/london/20260924T120000Z.json"), None
    )

    assert result["anomaly"] is False
    scan = handler.table.scan()
    assert scan["Count"] == 1


def test_high_temp_flags_anomaly(aws_env):
    s3, ddb = aws_env
    handler.table = ddb.Table("test-processed-data")
    s3.put_object(
        Bucket="test-raw-bucket",
        Key="raw/delhi/20260924T120000Z.json",
        Body=json.dumps({"name": "Delhi", "main": {"temp": 45.0, "humidity": 20}}),
    )

    result = handler.lambda_handler(
        _make_event("test-raw-bucket", "raw/delhi/20260924T120000Z.json"), None
    )

    assert result["anomaly"] is True
    assert "Delhi" in result["message"]


def test_malformed_payload_raises(aws_env):
    s3, ddb = aws_env
    handler.table = ddb.Table("test-processed-data")
    s3.put_object(
        Bucket="test-raw-bucket",
        Key="raw/broken/20260924T120000Z.json",
        Body=json.dumps({"unexpected": "shape"}),
    )

    with pytest.raises(ValueError):
        handler.lambda_handler(
            _make_event("test-raw-bucket", "raw/broken/20260924T120000Z.json"), None
        )
