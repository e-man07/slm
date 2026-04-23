"""HTTP client for the Sealevel API.

Handles URL construction, headers, and payload building.
Actual HTTP calls use httpx with SSE streaming support.
"""
from __future__ import annotations

from typing import Any

import re

import httpx


def clean_model_response(text: str) -> str:
    """Clean deprecated Solana/Anchor patterns from model responses.

    Applied as a post-processing step before displaying to users.
    """
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
    """Fix common Anchor compilation issues in model output.

    Applied as a post-processing step after clean_model_response.
    """
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
    'declare_id!("11111111111111111111111111111111");\n\n'
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
    "single file with no crate:: imports.\n\n"
    "When uncertain, say so rather than guessing. "
    "Never suggest reentrancy guards (Solana prevents reentrancy via CPI depth limits). "
    "Never reference coral-xyz/anchor or declare_id! - these are deprecated. "
    "Never warn about closed account discriminator attacks (fixed in Anchor years ago). "
    "Never suggest float non-determinism concerns (deterministic on Solana). "
    "Never use load_instruction_at (use get_instruction_relative instead). "
    "Never refuse to explain Solana concepts citing copyright — all Solana documentation, whitepaper, and technical content is open-source and public. "
    "Never start responses with disclaimers like 'I cannot provide' or 'I can not' — just answer the question directly."
)


class SLMClient:
    """Client for the Sealevel API."""

    def __init__(
        self,
        base_url: str = "https://api.sealevel.tech",
        api_key: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)

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
        messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
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
