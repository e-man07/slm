"""
Feature 22: Python CLI - Client URL construction tests

RED  - tests expect client module with URL building
GREEN - implement slm_cli/client.py
"""
import pytest


def test_client_module_importable():
    from slm_cli import client
    assert hasattr(client, "SLMClient")


def test_client_default_base_url():
    from slm_cli.client import SLMClient
    c = SLMClient()
    assert c.base_url == "https://slm.dev/api"


def test_client_custom_base_url():
    from slm_cli.client import SLMClient
    c = SLMClient(base_url="http://localhost:3000/api")
    assert c.base_url == "http://localhost:3000/api"


def test_client_chat_url():
    from slm_cli.client import SLMClient
    c = SLMClient(base_url="https://slm.dev/api")
    assert c.chat_url == "https://slm.dev/api/chat"


def test_client_explain_tx_url():
    from slm_cli.client import SLMClient
    c = SLMClient(base_url="https://slm.dev/api")
    assert c.explain_tx_url == "https://slm.dev/api/explain/tx"


def test_client_explain_error_url():
    from slm_cli.client import SLMClient
    c = SLMClient(base_url="https://slm.dev/api")
    assert c.explain_error_url == "https://slm.dev/api/explain/error"


def test_client_headers_without_api_key():
    from slm_cli.client import SLMClient
    c = SLMClient()
    headers = c.build_headers()
    assert "Content-Type" in headers
    assert headers["Content-Type"] == "application/json"
    assert "Authorization" not in headers


def test_client_headers_with_api_key():
    from slm_cli.client import SLMClient
    c = SLMClient(api_key="slm_test123")
    headers = c.build_headers()
    assert headers["Authorization"] == "Bearer slm_test123"


def test_client_chat_payload():
    from slm_cli.client import SLMClient
    c = SLMClient()
    payload = c.build_chat_payload("Hello, SLM!")
    assert "messages" in payload
    assert payload["messages"][-1]["role"] == "user"
    assert payload["messages"][-1]["content"] == "Hello, SLM!"
    assert payload["stream"] is True


def test_client_explain_error_payload():
    from slm_cli.client import SLMClient
    c = SLMClient()
    payload = c.build_error_payload("0x1771")
    assert payload["error_code"] == "0x1771"


def test_client_explain_tx_payload():
    from slm_cli.client import SLMClient
    c = SLMClient()
    payload = c.build_tx_payload("abc123sig")
    assert payload["signature"] == "abc123sig"
