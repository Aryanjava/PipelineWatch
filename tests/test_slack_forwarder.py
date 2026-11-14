import json
import os
from unittest.mock import patch, MagicMock

os.environ.setdefault("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/fake")

from lambdas.slack_forwarder import handler  # noqa: E402


def _sns_event(message, subject="PipelineWatch Alert"):
    return {
        "Records": [
            {"Sns": {"Message": message, "Subject": subject}}
        ]
    }


def test_forwards_message_to_slack():
    fake_resp = MagicMock()
    fake_resp.__enter__.return_value.status = 200

    with patch(
        "lambdas.slack_forwarder.handler.urllib.request.urlopen",
        return_value=fake_resp,
    ) as mock_urlopen:
        result = handler.lambda_handler(_sns_event("Delhi reported 45C"), None)

    assert result["forwarded"] == 1
    sent_request = mock_urlopen.call_args[0][0]
    body = json.loads(sent_request.data.decode())
    assert "Delhi reported 45C" in body["text"]


def test_slack_failure_raises():
    fake_resp = MagicMock()
    fake_resp.__enter__.return_value.status = 500

    with patch(
        "lambdas.slack_forwarder.handler.urllib.request.urlopen",
        return_value=fake_resp,
    ):
        try:
            handler.lambda_handler(_sns_event("test"), None)
            assert False, "expected RuntimeError"
        except RuntimeError:
            pass
