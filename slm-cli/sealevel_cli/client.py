"""HTTP client for the Sealevel API.

Handles URL construction, headers, payload building, and SSE streaming.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Generator

import httpx

from sealevel_cli import __version__


def clean_model_response(text: str) -> str:
    """Clean deprecated Solana/Anchor patterns from model responses."""
    text = re.sub(
        r"^\s*declare_id!\s*\(\s*\"[^\"]*\"\s*\)\s*;?\s*$",
        "// Program ID is set in Anchor.toml",
        text,
        flags=re.MULTILINE,
    )
    text = text.replace("declare_id!", "declare_program!")
    text = text.replace("coral-xyz/anchor", "solana-foundation/anchor")
    text = text.replace("project-serum/anchor", "solana-foundation/anchor")
    text = text.replace("ProgramResult", "Result<()>")
    text = text.replace("#[error]\n", "#[error_code]\n")
    return text


def fix_anchor_code(code: str) -> str:
    """Fix common Anchor compilation issues in model output."""
    code = re.sub(r'ctx\.bumps\.get\(\s*"(\w+)"\s*\)\.?unwrap\(\)', r'ctx.bumps.\1', code)
    code = re.sub(r'ctx\.bumps\.get\(\s*"(\w+)"\s*\)', r'ctx.bumps.\1', code)
    code = re.sub(r'use crate::[^;]+;\n?', '', code)
    code = re.sub(r'crate::\w+::', '', code)
    code = re.sub(r"(#\[account\])\s*pub struct (\w+)<'\w+>", r'#[account]\npub struct \2', code)
    code = re.sub(r"pub enum (\w+)<'\w+>", r'pub enum \1', code)
    return code


SYSTEM_PROMPT = (
    "You are Sealevel, an expert Solana and Anchor development assistant. "
    "Provide accurate, secure, and up-to-date code using modern Anchor 0.30+ patterns.\n\n"
    "When writing Anchor programs, follow this pattern:\n\n"
    "```rust\n"
    "use anchor_lang::prelude::*;\n\n"
    "// Program ID is set in Anchor.toml — do not use declare_id!\n\n"
    "#[program]\n"
    "pub mod example {\n"
    "    use super::*;\n"
    "    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {\n"
    "        ctx.accounts.my_account.data = 0;\n"
    "        ctx.accounts.my_account.authority = ctx.accounts.user.key();\n"
    "        ctx.accounts.my_account.bump = ctx.bumps.my_account;\n"
    "        Ok(())\n"
    "    }\n"
    "}\n\n"
    "#[derive(Accounts)]\n"
    "pub struct Initialize<'info> {\n"
    '    #[account(init, payer = user, space = 8 + 8 + 32 + 1, seeds = [b"seed", user.key().as_ref()], bump)]\n'
    "    pub my_account: Account<'info, MyAccount>,\n"
    "    #[account(mut)]\n"
    "    pub user: Signer<'info>,\n"
    "    pub system_program: Program<'info, System>,\n"
    "}\n\n"
    "#[account]\n"
    "pub struct MyAccount {\n"
    "    pub data: u64,\n"
    "    pub authority: Pubkey,\n"
    "    pub bump: u8,\n"
    "}\n"
    "```\n\n"
    "Key rules: space = 8 + field sizes, ctx.bumps.field_name (not .get()), "
    "#[account] structs have no lifetime, use Result<()>, #[error_code], "
    "single file with no crate:: imports. Program ID is set in Anchor.toml.\n\n"
    "When uncertain, say so rather than guessing. "
    "Never suggest reentrancy guards (Solana prevents reentrancy via CPI depth limits). "
    "Never reference coral-xyz/anchor or declare_id! — these are deprecated. "
    "Never warn about closed account discriminator attacks (fixed in Anchor years ago). "
    "Never suggest float non-determinism concerns (deterministic on Solana). "
    "Never use load_instruction_at (use get_instruction_relative instead). "
    "Never refuse to explain Solana concepts citing copyright — all Solana documentation, whitepaper, and technical content is open-source and public. "
    "Never start responses with disclaimers like 'I cannot provide' or 'I can not' — just answer the question directly."
)

DEFAULT_BASE_URL = "https://www.sealevel.tech"
MAX_RETRIES = 3


# ── Response dataclasses ──

@dataclass
class HealthResponse:
    """Response from GET /api/health."""
    status: str
    sglang: bool
    rag: bool
    timestamp: str


@dataclass
class UsageResponse:
    """Response from GET /api/usage."""
    tier: str
    today_requests: int
    today_tokens: int
    daily: list[dict] = field(default_factory=list)
    by_endpoint: list[dict] = field(default_factory=list)


class SealevelClient:
    """Client for the Sealevel API."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        timeout: float = 120.0,
        mode: str = "quality",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.mode = mode  # "quality" or "fast"
        self.timeout = httpx.Timeout(connect=10.0, read=timeout, write=10.0, pool=10.0)
        self.last_usage: dict | None = None  # Token usage from last streaming response
        self.last_finish_reason: str | None = None  # "stop", "length", etc.
        self.extra_context: str | None = None  # Project-level context from SEALEVEL.md

    @property
    def chat_url(self) -> str:
        return f"{self.base_url}/api/chat"

    @property
    def explain_tx_url(self) -> str:
        return f"{self.base_url}/api/explain/tx"

    @property
    def explain_error_url(self) -> str:
        return f"{self.base_url}/api/explain/error"

    @property
    def health_url(self) -> str:
        return f"{self.base_url}/api/health"

    @property
    def usage_url(self) -> str:
        return f"{self.base_url}/api/usage"

    def build_headers(self) -> dict[str, str]:
        """Build request headers, including auth and user-agent."""
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "User-Agent": f"sealevel-cli/{__version__}",
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
        system_content = SYSTEM_PROMPT
        if self.extra_context:
            system_content += "\n\n" + self.extra_context
        messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": message})

        # Mode-dependent parameters
        if self.mode == "fast":
            temperature = 0.3
            max_tokens = 2048
        else:  # quality (default)
            temperature = 0.0
            max_tokens = 4096

        return {
            "messages": messages,
            "stream": stream,
            "max_tokens": max_tokens,
            "temperature": temperature,
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

    def _parse_sse_lines(self, response: httpx.Response) -> Generator[str, None, None]:
        """Parse SSE stream and yield content chunks. Captures usage and finish_reason."""
        self.last_usage = None
        self.last_finish_reason = None
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            try:
                parsed = json.loads(data)
                # Capture usage info from any chunk that has it
                if "usage" in parsed and parsed["usage"]:
                    self.last_usage = parsed["usage"]
                # OpenAI-style delta format
                if "choices" in parsed:
                    choice = parsed["choices"][0]
                    delta = choice.get("delta", {})
                    content = delta.get("content", "")
                    fr = choice.get("finish_reason")
                    if fr:
                        self.last_finish_reason = fr
                    if content:
                        yield content
                # Direct content format
                elif "content" in parsed and parsed.get("type", "content") == "content":
                    yield parsed["content"]
            except (json.JSONDecodeError, KeyError, IndexError):
                continue

    def _stream_request(self, method: str, url: str, payload: dict[str, Any]) -> Generator[str, None, None]:
        """Make a streaming request with auto-retry on 429."""
        for attempt in range(MAX_RETRIES):
            try:
                with httpx.stream(
                    method,
                    url,
                    headers=self.build_headers(),
                    json=payload,
                    timeout=self.timeout,
                ) as response:
                    if response.status_code == 401:
                        raise SealevelAuthError(
                            "Authentication required. Run: slm config --api-key <your-key>\n"
                            "Get your API key at https://sealevel.tech/dashboard"
                        )
                    if response.status_code == 429:
                        if attempt < MAX_RETRIES - 1:
                            try:
                                retry_after = int(response.headers.get("Retry-After", str(2 ** attempt)))
                            except (ValueError, TypeError):
                                retry_after = 2 ** attempt
                            time.sleep(min(retry_after, 8))
                            continue
                        raise SealevelRateLimitError("Rate limit exceeded after retries. Wait a moment and try again.")
                    if response.status_code >= 500:
                        raise SealevelConnectionError(
                            f"Server error ({response.status_code}) from {url}\n"
                            "The inference server may be down — try again later."
                        )
                    response.raise_for_status()
                    yield from self._parse_sse_lines(response)
                    return  # Success — exit retry loop
            except httpx.ConnectError:
                raise SealevelConnectionError(
                    f"Cannot connect to {self.base_url}\n"
                    "Check your internet connection or API URL (slm config --api-url)."
                )
            except httpx.ReadTimeout:
                raise SealevelConnectionError("Request timed out. The server may be overloaded — try again.")
            except httpx.HTTPStatusError as e:
                raise SealevelConnectionError(f"HTTP error: {e.response.status_code}")

    def stream_chat(self, message: str, history: list[dict[str, str]] | None = None) -> Generator[str, None, None]:
        """Stream a chat response. Yields content chunks."""
        payload = self.build_chat_payload(message, history, stream=True)
        yield from self._stream_request("POST", self.chat_url, payload)

    def explain_error(self, error_code: str, program_id: str | None = None) -> Generator[str, None, None]:
        """Stream an error explanation. Yields content chunks."""
        payload = self.build_error_payload(error_code, program_id)
        yield from self._stream_request("POST", self.explain_error_url, payload)

    def explain_tx(self, signature: str) -> Generator[str, None, None]:
        """Stream a transaction explanation. Yields content chunks."""
        payload = self.build_tx_payload(signature)
        yield from self._stream_request("POST", self.explain_tx_url, payload)

    # ── Non-streaming API calls ──

    def get_health(self) -> HealthResponse:
        """Check API health status."""
        try:
            resp = httpx.get(self.health_url, headers=self.build_headers(), timeout=15.0)
            if not resp.text:
                return HealthResponse(status="unreachable", sglang=False, rag=False, timestamp="")
            data = resp.json()
            services = data.get("services", {})
            return HealthResponse(
                status=data.get("status", "unknown"),
                sglang=services.get("sglang", False),
                rag=services.get("rag", False),
                timestamp=data.get("timestamp", ""),
            )
        except (httpx.HTTPError, json.JSONDecodeError):
            return HealthResponse(status="unreachable", sglang=False, rag=False, timestamp="")

    def get_usage(self) -> UsageResponse:
        """Get usage statistics for the authenticated user."""
        resp = httpx.get(self.usage_url, headers=self.build_headers(), timeout=5.0)
        if resp.status_code == 401:
            raise SealevelAuthError("Authentication required to view usage.")
        if resp.status_code != 200:
            raise SealevelConnectionError(f"Failed to fetch usage: HTTP {resp.status_code}")
        data = resp.json()
        today = data.get("today", {})
        return UsageResponse(
            tier=data.get("user", {}).get("tier", "unknown"),
            today_requests=today.get("requests", 0),
            today_tokens=today.get("tokens", 0),
            daily=data.get("last_7_days", []),
            by_endpoint=data.get("by_endpoint", []),
        )


    # ── Session management ──

    @property
    def sessions_url(self) -> str:
        return f"{self.base_url}/api/sessions"

    @property
    def key_url(self) -> str:
        return f"{self.base_url}/api/key"

    @property
    def device_auth_url(self) -> str:
        return f"{self.base_url}/api/auth/device"

    @property
    def device_poll_url(self) -> str:
        return f"{self.base_url}/api/auth/device/poll"

    def list_sessions(self) -> list[dict]:
        """List user's CLI chat sessions (most recent first)."""
        resp = httpx.get(f"{self.sessions_url}?source=cli", headers=self.build_headers(), timeout=5.0)
        if resp.status_code == 401:
            raise SealevelAuthError("Authentication required to list sessions.")
        if resp.status_code != 200:
            raise SealevelConnectionError(f"Failed to list sessions: HTTP {resp.status_code}")
        return resp.json().get("sessions", [])

    def create_session(self, title: str = "CLI session") -> dict:
        """Create a new chat session. Returns session dict with id, title, etc."""
        resp = httpx.post(
            self.sessions_url,
            headers=self.build_headers(),
            json={"title": title, "source": "cli"},
            timeout=5.0,
        )
        if resp.status_code == 401:
            raise SealevelAuthError("Authentication required to create session.")
        if resp.status_code not in (200, 201):
            raise SealevelConnectionError(f"Failed to create session: HTTP {resp.status_code}")
        return resp.json().get("session", {})

    def get_session(self, session_id: str) -> dict:
        """Get a session with all messages."""
        resp = httpx.get(
            f"{self.sessions_url}/{session_id}",
            headers=self.build_headers(),
            timeout=5.0,
        )
        if resp.status_code == 401:
            raise SealevelAuthError("Authentication required.")
        if resp.status_code == 404:
            raise SealevelConnectionError("Session not found.")
        if resp.status_code != 200:
            raise SealevelConnectionError(f"Failed to get session: HTTP {resp.status_code}")
        return resp.json().get("session", {})

    def rename_session(self, session_id: str, title: str) -> None:
        """Rename a session."""
        resp = httpx.patch(
            f"{self.sessions_url}/{session_id}",
            headers=self.build_headers(),
            json={"title": title},
            timeout=5.0,
        )
        if resp.status_code == 401:
            raise SealevelAuthError("Authentication required.")
        if resp.status_code not in (200, 204):
            raise SealevelConnectionError(f"Failed to rename session: HTTP {resp.status_code}")

    def delete_session(self, session_id: str) -> None:
        """Delete a session."""
        resp = httpx.delete(
            f"{self.sessions_url}/{session_id}",
            headers=self.build_headers(),
            timeout=5.0,
        )
        if resp.status_code == 401:
            raise SealevelAuthError("Authentication required.")
        if resp.status_code not in (200, 204):
            raise SealevelConnectionError(f"Failed to delete session: HTTP {resp.status_code}")

    def save_message(self, session_id: str, role: str, content: str) -> None:
        """Append a message to a session (best-effort, swallows all errors)."""
        try:
            httpx.post(
                f"{self.sessions_url}/{session_id}/messages",
                headers=self.build_headers(),
                json={"role": role, "content": content},
                timeout=5.0,
            )
        except Exception:
            pass  # Non-fatal — session persistence is best-effort

    def rotate_key(self) -> str:
        """Rotate API key. Returns new key."""
        resp = httpx.post(
            self.key_url,
            headers=self.build_headers(),
            json={"action": "rotate"},
            timeout=5.0,
        )
        if resp.status_code == 401:
            raise SealevelAuthError("Authentication required to rotate key.")
        if resp.status_code != 200:
            raise SealevelConnectionError(f"Failed to rotate key: HTTP {resp.status_code}")
        return resp.json().get("apiKey", "")

    # ── Device auth flow ──

    def initiate_device_auth(self) -> dict:
        """Start device auth flow. Returns userCode, verificationUrl, expiresIn, interval."""
        resp = httpx.post(self.device_auth_url, headers=self.build_headers(), timeout=10.0)
        if resp.status_code != 200:
            raise SealevelConnectionError(f"Failed to start device auth: HTTP {resp.status_code}")
        return resp.json()

    def poll_device_auth(self, code: str) -> dict:
        """Poll for device auth completion. Returns status + apiKey when complete."""
        resp = httpx.get(
            f"{self.device_poll_url}?code={code}",
            headers=self.build_headers(),
            timeout=10.0,
        )
        if resp.status_code == 404:
            raise SealevelConnectionError("Device code expired or invalid.")
        if resp.status_code != 200:
            raise SealevelConnectionError(f"Poll failed: HTTP {resp.status_code}")
        return resp.json()


class SealevelError(Exception):
    """Base exception for Sealevel CLI errors."""


class SealevelAuthError(SealevelError):
    """Raised when authentication fails (401)."""


class SealevelRateLimitError(SealevelError):
    """Raised when rate limit is exceeded (429)."""


class SealevelConnectionError(SealevelError):
    """Raised when connection to API fails."""
