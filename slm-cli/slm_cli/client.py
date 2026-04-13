"""HTTP client for the SLM API.

Handles URL construction, headers, and payload building.
Actual HTTP calls use httpx with SSE streaming support.
"""
from __future__ import annotations

from typing import Any

import httpx


class SLMClient:
    """Client for the SLM API."""

    def __init__(
        self,
        base_url: str = "https://slm.dev/api",
        api_key: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    @property
    def chat_url(self) -> str:
        return f"{self.base_url}/chat"

    @property
    def explain_tx_url(self) -> str:
        return f"{self.base_url}/explain/tx"

    @property
    def explain_error_url(self) -> str:
        return f"{self.base_url}/explain/error"

    def build_headers(self) -> dict[str, str]:
        """Build request headers, optionally including auth."""
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def build_chat_payload(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
        stream: bool = True,
    ) -> dict[str, Any]:
        """Build the chat API request payload."""
        messages: list[dict[str, str]] = []
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": message})
        return {
            "messages": messages,
            "stream": stream,
            "max_tokens": 1024,
            "temperature": 0.0,
        }

    def build_error_payload(self, error_code: str, program_id: str | None = None) -> dict[str, Any]:
        """Build the explain-error API request payload."""
        payload: dict[str, Any] = {"error_code": error_code}
        if program_id:
            payload["program_id"] = program_id
        return payload

    def build_tx_payload(self, signature: str) -> dict[str, Any]:
        """Build the explain-tx API request payload."""
        return {"signature": signature}

    def stream_chat(self, message: str, history: list[dict[str, str]] | None = None):
        """Stream a chat response. Yields content chunks."""
        payload = self.build_chat_payload(message, history, stream=True)
        with httpx.stream(
            "POST",
            self.chat_url,
            headers=self.build_headers(),
            json=payload,
            timeout=self.timeout,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    import json
                    parsed = json.loads(data)
                    # Handle both direct content and OpenAI-style delta
                    if "content" in parsed:
                        yield parsed["content"]
                    elif "choices" in parsed:
                        delta = parsed["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

    def explain_error(self, error_code: str, program_id: str | None = None):
        """Stream an error explanation. Yields content chunks."""
        payload = self.build_error_payload(error_code, program_id)
        with httpx.stream(
            "POST",
            self.explain_error_url,
            headers=self.build_headers(),
            json=payload,
            timeout=self.timeout,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    import json
                    parsed = json.loads(data)
                    if parsed.get("type") == "content":
                        yield parsed["content"]
                except (json.JSONDecodeError, KeyError):
                    continue

    def explain_tx(self, signature: str):
        """Stream a transaction explanation. Yields content chunks."""
        payload = self.build_tx_payload(signature)
        with httpx.stream(
            "POST",
            self.explain_tx_url,
            headers=self.build_headers(),
            json=payload,
            timeout=self.timeout,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    import json
                    parsed = json.loads(data)
                    if parsed.get("type") == "content":
                        yield parsed["content"]
                except (json.JSONDecodeError, KeyError):
                    continue
