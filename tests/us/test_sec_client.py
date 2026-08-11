import json

import pytest

from adapter.errors import SecRequestError
from adapter.sec_client import SecClient


def test_get_json_uses_declared_user_agent():
    seen = {}

    def transport(url, headers, timeout):
        seen["url"] = url
        seen["user_agent"] = headers["User-Agent"]
        seen["timeout"] = timeout
        return json.dumps({"ok": True}).encode()

    client = SecClient(user_agent="test-agent contact@example.com", min_interval_seconds=0, transport=transport)
    assert client.get_json("https://data.sec.gov/example.json") == {"ok": True}
    assert seen == {
        "url": "https://data.sec.gov/example.json",
        "user_agent": "test-agent contact@example.com", "timeout": 40.0,
    }


def test_non_sec_url_is_rejected():
    client = SecClient(user_agent="test-agent contact@example.com")
    with pytest.raises(SecRequestError, match="non-SEC"):
        client.get_bytes("https://example.com/file.json")


def test_retry_is_bounded():
    attempts = []

    class RetryableError(Exception):
        code = 503

    def transport(_url, _headers, timeout):
        del timeout
        attempts.append(1)
        raise RetryableError("busy")

    client = SecClient(
        user_agent="test-agent contact@example.com",
        max_attempts=3,
        min_interval_seconds=0,
        sleep=lambda _seconds: None,
        transport=transport,
    )
    with pytest.raises(SecRequestError, match="3 attempt"):
        client.get_bytes("https://data.sec.gov/x")
    assert len(attempts) == 3
