"""Tests for sealevel_cli.client — URL construction, headers, payloads, SSE parsing, error handling."""
import json
import pytest
import httpx
from unittest.mock import MagicMock, patch

from sealevel_cli.client import (
    SealevelClient,
    SealevelAuthError,
    SealevelConnectionError,
    SealevelError,
    SealevelRateLimitError,
    DEFAULT_BASE_URL,
    MAX_RETRIES,
    clean_model_response,
    fix_anchor_code,
)


# --- Module and class basics ---


def test_client_module_importable():
    from sealevel_cli import client
    assert hasattr(client, "SealevelClient")


def test_client_default_base_url():
    c = SealevelClient()
    assert c.base_url == DEFAULT_BASE_URL


def test_client_custom_base_url():
    c = SealevelClient(base_url="http://localhost:3000/api")
    assert c.base_url == "http://localhost:3000/api"


def test_client_strips_trailing_slash():
    c = SealevelClient(base_url="https://www.sealevel.tech/")
    assert c.base_url == "https://www.sealevel.tech"


def test_client_timeout_used_in_httpx():
    c = SealevelClient(timeout=60.0)
    assert c.timeout.read == 60.0
    assert c.timeout.connect == 10.0


def test_client_default_timeout():
    c = SealevelClient()
    assert c.timeout.read == 120.0


# --- URL properties ---


def test_client_chat_url():
    c = SealevelClient(base_url="https://www.sealevel.tech")
    assert c.chat_url == "https://www.sealevel.tech/api/chat"


def test_client_explain_tx_url():
    c = SealevelClient(base_url="https://www.sealevel.tech")
    assert c.explain_tx_url == "https://www.sealevel.tech/api/explain/tx"


def test_client_explain_error_url():
    c = SealevelClient(base_url="https://www.sealevel.tech")
    assert c.explain_error_url == "https://www.sealevel.tech/api/explain/error"


# --- Headers ---


def test_headers_without_api_key():
    c = SealevelClient()
    headers = c.build_headers()
    assert headers["Content-Type"] == "application/json"
    assert "Authorization" not in headers


def test_headers_with_api_key():
    c = SealevelClient(api_key="slm_test123")
    headers = c.build_headers()
    assert headers["Authorization"] == "Bearer slm_test123"


def test_headers_include_user_agent():
    c = SealevelClient()
    headers = c.build_headers()
    assert "User-Agent" in headers
    assert headers["User-Agent"].startswith("sealevel-cli/")


# --- Payload building ---


def test_chat_payload_basic():
    c = SealevelClient()
    payload = c.build_chat_payload("Hello!")
    assert payload["messages"][-1] == {"role": "user", "content": "Hello!"}
    assert payload["messages"][0]["role"] == "system"
    assert payload["stream"] is True
    assert payload["max_tokens"] == 4096
    assert payload["temperature"] == 0.0


def test_chat_payload_with_history():
    c = SealevelClient()
    history = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello!"},
    ]
    payload = c.build_chat_payload("Follow up", history=history)
    messages = payload["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "user", "content": "Hi"}
    assert messages[2] == {"role": "assistant", "content": "Hello!"}
    assert messages[3] == {"role": "user", "content": "Follow up"}


def test_chat_payload_no_stream():
    c = SealevelClient()
    payload = c.build_chat_payload("Hello!", stream=False)
    assert payload["stream"] is False


def test_error_payload_basic():
    c = SealevelClient()
    payload = c.build_error_payload("0x1771")
    assert payload == {"error_code": "0x1771"}


def test_error_payload_with_program_id():
    c = SealevelClient()
    payload = c.build_error_payload("0x1771", program_id="TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
    assert payload["error_code"] == "0x1771"
    assert payload["program_id"] == "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


def test_tx_payload():
    c = SealevelClient()
    payload = c.build_tx_payload("5U3abc123")
    assert payload == {"signature": "5U3abc123"}


# --- SSE parsing ---


class FakeResponse:
    """Mock httpx response for SSE testing."""
    def __init__(self, lines, status_code=200):
        self._lines = lines
        self.status_code = status_code

    def iter_lines(self):
        return iter(self._lines)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def test_parse_sse_openai_format():
    c = SealevelClient()
    lines = [
        'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        'data: {"choices":[{"delta":{"content":" world"}}]}',
        'data: [DONE]',
    ]
    resp = FakeResponse(lines)
    chunks = list(c._parse_sse_lines(resp))
    assert chunks == ["Hello", " world"]


def test_parse_sse_direct_content_format():
    c = SealevelClient()
    lines = [
        'data: {"type":"content","content":"chunk1"}',
        'data: {"type":"content","content":"chunk2"}',
        'data: [DONE]',
    ]
    resp = FakeResponse(lines)
    chunks = list(c._parse_sse_lines(resp))
    assert chunks == ["chunk1", "chunk2"]


def test_parse_sse_skips_non_data_lines():
    c = SealevelClient()
    lines = [
        ': heartbeat',
        'event: ping',
        'data: {"choices":[{"delta":{"content":"ok"}}]}',
        '',
        'data: [DONE]',
    ]
    resp = FakeResponse(lines)
    chunks = list(c._parse_sse_lines(resp))
    assert chunks == ["ok"]


def test_parse_sse_skips_malformed_json():
    c = SealevelClient()
    lines = [
        'data: {broken json',
        'data: {"choices":[{"delta":{"content":"good"}}]}',
        'data: [DONE]',
    ]
    resp = FakeResponse(lines)
    chunks = list(c._parse_sse_lines(resp))
    assert chunks == ["good"]


def test_parse_sse_empty_delta_content():
    c = SealevelClient()
    lines = [
        'data: {"choices":[{"delta":{}}]}',
        'data: {"choices":[{"delta":{"content":""}}]}',
        'data: {"choices":[{"delta":{"content":"real"}}]}',
        'data: [DONE]',
    ]
    resp = FakeResponse(lines)
    chunks = list(c._parse_sse_lines(resp))
    assert chunks == ["real"]


def test_parse_sse_skips_tx_data_events():
    """explain/tx sends type=tx_data first, then type=content. Only content should be yielded."""
    c = SealevelClient()
    lines = [
        'data: {"type":"tx_data","data":{"signature":"abc"}}',
        'data: {"type":"content","content":"Explanation here"}',
        'data: [DONE]',
    ]
    resp = FakeResponse(lines)
    chunks = list(c._parse_sse_lines(resp))
    assert chunks == ["Explanation here"]


def test_parse_sse_captures_usage():
    """Usage info from final SSE chunk should be stored in client.last_usage."""
    c = SealevelClient()
    lines = [
        'data: {"choices":[{"delta":{"content":"hi"}}]}',
        'data: {"choices":[{"delta":{"content":"!"}}],"usage":{"total_tokens":500,"prompt_tokens":400,"completion_tokens":100}}',
        'data: [DONE]',
    ]

    class FakeResp:
        def iter_lines(self):
            return iter(lines)

    chunks = list(c._parse_sse_lines(FakeResp()))
    assert chunks == ["hi", "!"]
    assert c.last_usage is not None
    assert c.last_usage["total_tokens"] == 500


def test_parse_sse_usage_overwritten_by_later_chunk():
    """If multiple chunks have usage, last one wins."""
    c = SealevelClient()
    lines = [
        'data: {"choices":[{"delta":{"content":"a"}}],"usage":{"total_tokens":100}}',
        'data: {"choices":[{"delta":{"content":"b"}}],"usage":{"total_tokens":500}}',
        'data: [DONE]',
    ]

    class FakeResp:
        def iter_lines(self):
            return iter(lines)

    list(c._parse_sse_lines(FakeResp()))
    assert c.last_usage["total_tokens"] == 500


def test_parse_sse_captures_finish_reason():
    c = SealevelClient()
    lines = [
        'data: {"choices":[{"delta":{"content":"hi"},"finish_reason":null}]}',
        'data: {"choices":[{"delta":{"content":"!"},"finish_reason":"length"}]}',
        'data: [DONE]',
    ]

    class FakeResp:
        def iter_lines(self):
            return iter(lines)

    list(c._parse_sse_lines(FakeResp()))
    assert c.last_finish_reason == "length"


def test_parse_sse_finish_reason_stop():
    c = SealevelClient()
    lines = [
        'data: {"choices":[{"delta":{"content":"done"},"finish_reason":"stop"}]}',
        'data: [DONE]',
    ]

    class FakeResp:
        def iter_lines(self):
            return iter(lines)

    list(c._parse_sse_lines(FakeResp()))
    assert c.last_finish_reason == "stop"


def test_parse_sse_finish_reason_reset():
    """finish_reason should reset to None at start of each parse."""
    c = SealevelClient()
    c.last_finish_reason = "length"  # From previous call
    lines = [
        'data: {"choices":[{"delta":{"content":"ok"}}]}',
        'data: [DONE]',
    ]

    class FakeResp:
        def iter_lines(self):
            return iter(lines)

    list(c._parse_sse_lines(FakeResp()))
    assert c.last_finish_reason is None


def test_extra_context_in_payload():
    c = SealevelClient()
    c.extra_context = "Always use Anchor 0.30+"
    payload = c.build_chat_payload("hello")
    system_msg = payload["messages"][0]["content"]
    assert "Always use Anchor 0.30+" in system_msg


def test_no_extra_context_in_payload():
    c = SealevelClient()
    c.extra_context = None
    payload = c.build_chat_payload("hello")
    system_msg = payload["messages"][0]["content"]
    assert "Always use Anchor" not in system_msg


def test_parse_sse_no_usage():
    c = SealevelClient()
    lines = [
        'data: {"choices":[{"delta":{"content":"ok"}}]}',
        'data: [DONE]',
    ]

    class FakeResp:
        def iter_lines(self):
            return iter(lines)

    list(c._parse_sse_lines(FakeResp()))
    assert c.last_usage is None


def test_parse_sse_skips_lookup_events():
    """explain/error sends type=lookup first, then type=content."""
    c = SealevelClient()
    lines = [
        'data: {"type":"lookup","data":{"code":6000}}',
        'data: {"type":"content","content":"Error means X"}',
        'data: [DONE]',
    ]
    resp = FakeResponse(lines)
    chunks = list(c._parse_sse_lines(resp))
    assert chunks == ["Error means X"]


# --- Error handling ---


def test_stream_request_auth_error():
    c = SealevelClient()
    with patch("httpx.stream") as mock_stream:
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_stream.return_value = mock_resp

        with pytest.raises(SealevelAuthError, match="Authentication required"):
            list(c._stream_request("POST", c.chat_url, {}))


def test_stream_request_rate_limit_error():
    c = SealevelClient()
    with patch("httpx.stream") as mock_stream:
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_stream.return_value = mock_resp

        with pytest.raises(SealevelRateLimitError, match="Rate limit"):
            list(c._stream_request("POST", c.chat_url, {}))


def test_stream_request_connection_error():
    import httpx as _httpx
    c = SealevelClient()
    with patch("httpx.stream", side_effect=_httpx.ConnectError("refused")):
        with pytest.raises(SealevelConnectionError, match="Cannot connect"):
            list(c._stream_request("POST", c.chat_url, {}))


def test_stream_request_timeout_error():
    import httpx as _httpx
    c = SealevelClient()
    with patch("httpx.stream", side_effect=_httpx.ReadTimeout("timeout")):
        with pytest.raises(SealevelConnectionError, match="timed out"):
            list(c._stream_request("POST", c.chat_url, {}))


def test_stream_request_server_error_500():
    c = SealevelClient()
    with patch("httpx.stream") as mock_stream:
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_stream.return_value = mock_resp

        with pytest.raises(SealevelConnectionError, match="Server error"):
            list(c._stream_request("POST", c.chat_url, {}))


def test_stream_request_server_error_502():
    c = SealevelClient()
    with patch("httpx.stream") as mock_stream:
        mock_resp = MagicMock()
        mock_resp.status_code = 502
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_stream.return_value = mock_resp

        with pytest.raises(SealevelConnectionError, match="Server error"):
            list(c._stream_request("POST", c.chat_url, {}))


def test_stream_request_http_status_error():
    import httpx as _httpx
    c = SealevelClient()
    mock_response = MagicMock()
    mock_response.status_code = 418
    with patch("httpx.stream") as mock_stream:
        mock_resp = MagicMock()
        mock_resp.status_code = 418
        mock_resp.raise_for_status.side_effect = _httpx.HTTPStatusError(
            "teapot", request=MagicMock(), response=mock_response
        )
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_stream.return_value = mock_resp

        with pytest.raises(SealevelConnectionError, match="HTTP error"):
            list(c._stream_request("POST", c.chat_url, {}))


# --- Exception hierarchy ---


def test_stream_request_retries_on_429():
    """429 should retry up to MAX_RETRIES times before raising."""
    c = SealevelClient()
    call_count = 0

    def mock_stream(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_resp = MagicMock()
        if call_count < 3:
            mock_resp.status_code = 429
            mock_resp.headers = {"Retry-After": "0"}
        else:
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
            mock_resp.iter_lines.return_value = iter([
                'data: {"choices":[{"delta":{"content":"ok"}}]}',
                'data: [DONE]',
            ])
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    with patch("httpx.stream", side_effect=mock_stream):
        with patch("time.sleep"):  # Don't actually sleep
            chunks = list(c._stream_request("POST", c.chat_url, {}))
    assert chunks == ["ok"]
    assert call_count == 3


def test_stream_request_429_exhausts_retries():
    c = SealevelClient()

    def mock_stream(*args, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {"Retry-After": "0"}
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    with patch("httpx.stream", side_effect=mock_stream):
        with patch("time.sleep"):
            with pytest.raises(SealevelRateLimitError, match="after retries"):
                list(c._stream_request("POST", c.chat_url, {}))


# --- Non-streaming API calls ---


def test_get_health_success():
    c = SealevelClient()
    with patch("httpx.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            text='{"status":"ok"}',
            json=lambda: {"status": "ok", "services": {"sglang": True, "rag": False}, "timestamp": "2026-01-01"},
        )
        health = c.get_health()
    assert health.status == "ok"
    assert health.sglang is True
    assert health.rag is False


def test_get_health_unreachable():
    c = SealevelClient()
    with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
        health = c.get_health()
    assert health.status == "unreachable"


def test_get_health_empty_response():
    c = SealevelClient()
    with patch("httpx.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, text="")
        health = c.get_health()
    assert health.status == "unreachable"


def test_get_usage_success():
    c = SealevelClient(api_key="slm_test123")
    with patch("httpx.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "user": {"tier": "free"},
                "today": {"requests": 10, "tokens": 5000},
                "last_7_days": [{"date": "2026-01-01", "requests": 10, "tokens": 5000}],
                "by_endpoint": [],
            },
        )
        usage = c.get_usage()
    assert usage.tier == "free"
    assert usage.today_requests == 10
    assert usage.today_tokens == 5000
    assert len(usage.daily) == 1


def test_get_usage_401():
    c = SealevelClient()
    with patch("httpx.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=401)
        with pytest.raises(SealevelAuthError):
            c.get_usage()


def test_health_url():
    c = SealevelClient(base_url="https://www.sealevel.tech")
    assert c.health_url == "https://www.sealevel.tech/api/health"


def test_usage_url():
    c = SealevelClient(base_url="https://www.sealevel.tech")
    assert c.usage_url == "https://www.sealevel.tech/api/usage"


# --- Retry edge cases ---


def test_stream_request_retry_caps_at_8s():
    c = SealevelClient()
    call_count = 0

    def mock_stream(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_resp = MagicMock()
        if call_count == 1:
            mock_resp.status_code = 429
            mock_resp.headers = {"Retry-After": "999"}  # Should be capped to 8
        else:
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
            mock_resp.iter_lines.return_value = iter(['data: [DONE]'])
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    with patch("httpx.stream", side_effect=mock_stream):
        with patch("time.sleep") as mock_sleep:
            list(c._stream_request("POST", c.chat_url, {}))
            mock_sleep.assert_called_once_with(8)


def test_stream_request_retry_after_malformed():
    c = SealevelClient()
    call_count = 0

    def mock_stream(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_resp = MagicMock()
        if call_count == 1:
            mock_resp.status_code = 429
            mock_resp.headers = {"Retry-After": "not-a-number"}
        else:
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
            mock_resp.iter_lines.return_value = iter(['data: [DONE]'])
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    with patch("httpx.stream", side_effect=mock_stream):
        with patch("time.sleep") as mock_sleep:
            list(c._stream_request("POST", c.chat_url, {}))
            # Should use 2^0 = 1 as fallback
            mock_sleep.assert_called_once_with(1)


# --- Session client methods ---


def test_sessions_url():
    c = SealevelClient(base_url="https://www.sealevel.tech")
    assert c.sessions_url == "https://www.sealevel.tech/api/sessions"


def test_key_url():
    c = SealevelClient(base_url="https://www.sealevel.tech")
    assert c.key_url == "https://www.sealevel.tech/api/key"


def test_list_sessions_success():
    c = SealevelClient(api_key="slm_test123")
    with patch("httpx.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"sessions": [{"id": "s1", "title": "Test"}]},
        )
        result = c.list_sessions()
    assert len(result) == 1
    assert result[0]["id"] == "s1"


def test_list_sessions_401():
    c = SealevelClient()
    with patch("httpx.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=401)
        with pytest.raises(SealevelAuthError):
            c.list_sessions()


def test_create_session_success():
    c = SealevelClient(api_key="slm_test123")
    with patch("httpx.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=201,
            json=lambda: {"session": {"id": "new-1", "title": "CLI session"}},
        )
        result = c.create_session()
    assert result["id"] == "new-1"


def test_create_session_401():
    c = SealevelClient()
    with patch("httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=401)
        with pytest.raises(SealevelAuthError):
            c.create_session()


def test_get_session_success():
    c = SealevelClient(api_key="slm_test123")
    with patch("httpx.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"session": {"id": "s1", "messages": []}},
        )
        result = c.get_session("s1")
    assert result["id"] == "s1"


def test_get_session_404():
    c = SealevelClient(api_key="slm_test123")
    with patch("httpx.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=404)
        with pytest.raises(SealevelConnectionError, match="not found"):
            c.get_session("nonexistent")


def test_rename_session_success():
    c = SealevelClient(api_key="slm_test123")
    with patch("httpx.patch") as mock_patch:
        mock_patch.return_value = MagicMock(status_code=200)
        c.rename_session("s1", "New Title")  # Should not raise


def test_delete_session_success():
    c = SealevelClient(api_key="slm_test123")
    with patch("httpx.delete") as mock_del:
        mock_del.return_value = MagicMock(status_code=200)
        c.delete_session("s1")  # Should not raise


def test_delete_session_401():
    c = SealevelClient()
    with patch("httpx.delete") as mock_del:
        mock_del.return_value = MagicMock(status_code=401)
        with pytest.raises(SealevelAuthError):
            c.delete_session("s1")


def test_save_message_connection_error():
    c = SealevelClient(api_key="slm_test123")
    with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
        c.save_message("s1", "user", "hello")  # Should not raise


def test_save_message_success():
    c = SealevelClient(api_key="slm_test123")
    with patch("httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=201)
        c.save_message("s1", "user", "hello")  # Should not raise


def test_rotate_key_success():
    c = SealevelClient(api_key="slm_test123")
    with patch("httpx.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"apiKey": "slm_newkey999"},
        )
        result = c.rotate_key()
    assert result == "slm_newkey999"


def test_rotate_key_401():
    c = SealevelClient()
    with patch("httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=401)
        with pytest.raises(SealevelAuthError):
            c.rotate_key()


def test_get_usage_503():
    c = SealevelClient(api_key="slm_test123")
    with patch("httpx.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=503)
        with pytest.raises(SealevelConnectionError):
            c.get_usage()


# --- Exception hierarchy ---


def test_all_errors_inherit_from_sealevel_error():
    assert issubclass(SealevelAuthError, SealevelError)
    assert issubclass(SealevelRateLimitError, SealevelError)
    assert issubclass(SealevelConnectionError, SealevelError)


# --- Issue #1: max_tokens should be 4096 not 1024 ---


def test_chat_payload_max_tokens_4096():
    """max_tokens must be 4096 to avoid constant truncation on code gen."""
    c = SealevelClient()
    payload = c.build_chat_payload("Generate an escrow program")
    assert payload["max_tokens"] == 4096


# --- Issue #5: system prompt sent every request (no fix needed, just verify) ---
# System prompt is expected per request — OpenAI-compatible format requires it.
# This is a verification test, not a bug fix.


# --- Issue #9/10/11: mode config wires to temperature + max_tokens ---


def test_chat_payload_quality_mode():
    """Quality mode: temperature 0.0, max_tokens 4096."""
    c = SealevelClient()
    c.mode = "quality"
    payload = c.build_chat_payload("hello")
    assert payload["temperature"] == 0.0
    assert payload["max_tokens"] == 4096


def test_chat_payload_fast_mode():
    """Fast mode: temperature 0.3, max_tokens 2048."""
    c = SealevelClient()
    c.mode = "fast"
    payload = c.build_chat_payload("hello")
    assert payload["temperature"] == 0.3
    assert payload["max_tokens"] == 2048


def test_client_default_mode():
    """Client default mode should be 'quality'."""
    c = SealevelClient()
    assert c.mode == "quality"


def test_client_custom_mode():
    """Client should accept mode parameter."""
    c = SealevelClient(mode="fast")
    assert c.mode == "fast"


# --- Issue #2: _stream_request silent fallthrough ---


def test_stream_request_no_silent_fallthrough():
    """If retry loop exhausts without return or raise, should raise error."""
    c = SealevelClient()
    call_count = 0

    def mock_stream(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {"Retry-After": "0"}
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    with patch("httpx.stream", side_effect=mock_stream):
        with patch("time.sleep"):
            with pytest.raises(SealevelRateLimitError):
                list(c._stream_request("POST", c.chat_url, {}))
    assert call_count == MAX_RETRIES


# --- Device auth flow ---


def test_device_auth_url():
    c = SealevelClient(base_url="https://www.sealevel.tech")
    assert c.device_auth_url == "https://www.sealevel.tech/api/auth/device"


def test_device_poll_url():
    c = SealevelClient(base_url="https://www.sealevel.tech")
    assert c.device_poll_url == "https://www.sealevel.tech/api/auth/device/poll"


def test_initiate_device_auth():
    c = SealevelClient()
    with patch("httpx.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "userCode": "ABCD-1234",
                "verificationUrl": "https://sealevel.tech/device",
                "expiresIn": 600,
                "interval": 5,
            },
        )
        result = c.initiate_device_auth()
    assert result["userCode"] == "ABCD-1234"
    assert result["verificationUrl"] == "https://sealevel.tech/device"
    assert result["expiresIn"] == 600


def test_poll_device_auth_pending():
    c = SealevelClient()
    with patch("httpx.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"status": "pending"},
        )
        result = c.poll_device_auth("ABCD-1234")
    assert result["status"] == "pending"
    assert "apiKey" not in result


def test_poll_device_auth_complete():
    c = SealevelClient()
    with patch("httpx.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "status": "complete",
                "apiKey": "slm_newkey123456",
                "user": {"name": "kshitij", "tier": "free"},
            },
        )
        result = c.poll_device_auth("ABCD-1234")
    assert result["status"] == "complete"
    assert result["apiKey"] == "slm_newkey123456"
    assert result["user"]["name"] == "kshitij"


def test_poll_device_auth_expired():
    c = SealevelClient()
    with patch("httpx.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=404)
        with pytest.raises(SealevelConnectionError, match="expired"):
            c.poll_device_auth("XXXX-9999")


def test_initiate_device_auth_failure():
    c = SealevelClient()
    with patch("httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=500)
        with pytest.raises(SealevelConnectionError, match="Failed to start device auth"):
            c.initiate_device_auth()


def test_poll_device_auth_server_error():
    c = SealevelClient()
    with patch("httpx.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=500)
        with pytest.raises(SealevelConnectionError, match="Poll failed"):
            c.poll_device_auth("CODE-123")


def test_list_sessions_server_error():
    c = SealevelClient(api_key="slm_test123")
    with patch("httpx.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=500)
        with pytest.raises(SealevelConnectionError, match="Failed to list sessions"):
            c.list_sessions()


def test_chat_payload_unknown_mode_falls_to_quality():
    """Invalid mode should fall through to quality defaults."""
    c = SealevelClient(mode="turbo")
    payload = c.build_chat_payload("hello")
    assert payload["temperature"] == 0.0
    assert payload["max_tokens"] == 4096


# --- Fix #5: System prompt no longer contains declare_id! ---


def test_system_prompt_no_declare_id_in_example_code():
    """System prompt example code should not use declare_id! (deprecated)."""
    from sealevel_cli.client import SYSTEM_PROMPT
    # Extract the code block from system prompt
    import re
    code_match = re.search(r"```rust\n(.*?)```", SYSTEM_PROMPT, re.DOTALL)
    assert code_match is not None
    code_block = code_match.group(1)
    # Code block should NOT contain declare_id! as actual code usage
    assert 'declare_id!("' not in code_block
    # But the instruction text may reference it (to say "don't use it")
    assert "do not use declare_id!" in SYSTEM_PROMPT or "Never reference" in SYSTEM_PROMPT


# --- clean_model_response ---


def test_clean_declare_id_line():
    code = '  declare_id!("ABC123");'
    cleaned = clean_model_response(code)
    assert "Program ID is set in Anchor.toml" in cleaned
    assert "declare_id!" not in cleaned


def test_clean_declare_id_inline():
    text = "Use declare_id! macro to set your program ID"
    cleaned = clean_model_response(text)
    assert "declare_program!" in cleaned
    assert "declare_id!" not in cleaned


def test_clean_coral_xyz():
    text = "Add coral-xyz/anchor to your Cargo.toml"
    cleaned = clean_model_response(text)
    assert "solana-foundation/anchor" in cleaned


def test_clean_project_serum():
    text = "Use project-serum/anchor"
    cleaned = clean_model_response(text)
    assert "solana-foundation/anchor" in cleaned


def test_clean_program_result():
    text = "fn handler() -> ProgramResult {"
    cleaned = clean_model_response(text)
    assert "Result<()>" in cleaned


def test_clean_error_attribute():
    text = "#[error]\npub enum MyError {"
    cleaned = clean_model_response(text)
    assert "#[error_code]\n" in cleaned


def test_clean_preserves_normal_code():
    code = "pub fn init(ctx: Context<Init>) -> Result<()> { Ok(()) }"
    assert clean_model_response(code) == code


# --- fix_anchor_code ---


def test_fix_bumps_get_unwrap():
    code = 'ctx.bumps.get("my_account").unwrap()'
    fixed = fix_anchor_code(code)
    assert fixed == "ctx.bumps.my_account"


def test_fix_bumps_get_without_unwrap():
    code = 'ctx.bumps.get("pda_account")'
    fixed = fix_anchor_code(code)
    assert fixed == "ctx.bumps.pda_account"


def test_fix_crate_imports():
    code = "use crate::state::MyState;\nuse crate::errors::MyError;\nfn foo() {}"
    fixed = fix_anchor_code(code)
    assert "crate::" not in fixed
    assert "fn foo() {}" in fixed


def test_fix_crate_path_inline():
    code = "let x = crate::state::MyAccount::default();"
    fixed = fix_anchor_code(code)
    assert "crate::" not in fixed
    assert "MyAccount::default()" in fixed


def test_fix_account_struct_lifetime():
    code = "#[account]\npub struct MyData<'info> {"
    fixed = fix_anchor_code(code)
    assert "<'info>" not in fixed
    assert "pub struct MyData {" in fixed


def test_fix_enum_lifetime():
    code = "pub enum MyError<'info> {"
    fixed = fix_anchor_code(code)
    assert "<'info>" not in fixed
    assert "pub enum MyError {" in fixed


def test_fix_preserves_accounts_struct_lifetime():
    """#[derive(Accounts)] structs should keep their lifetime — fix_anchor_code only targets #[account]."""
    code = "#[derive(Accounts)]\npub struct Init<'info> {"
    fixed = fix_anchor_code(code)
    assert "<'info>" in fixed  # Should be preserved
