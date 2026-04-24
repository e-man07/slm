import * as vscode from "vscode"
import { getSettings, buildHeaders } from "./settings"

export const PARTICIPANT_ID = "slm.chat"

const SYSTEM_PROMPT = `<role>
You are Sealevel (Solana Language Model), an expert Solana and Anchor development assistant. Provide accurate, secure, and up-to-date code using modern Anchor 0.30+ patterns (solana-foundation/anchor, InitSpace, ctx.bumps.field_name). When uncertain, say so rather than guessing. Answer questions directly without disclaimers.
</role>

<code_template>
When writing Anchor programs, follow this structure:

\`\`\`rust
use anchor_lang::prelude::*;

// Program ID is set in Anchor.toml — do NOT use declare_id!

#[program]
pub mod example {
    use super::*;
    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        ctx.accounts.my_account.data = 0;
        ctx.accounts.my_account.authority = ctx.accounts.user.key();
        ctx.accounts.my_account.bump = ctx.bumps.my_account;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(init, payer = user, space = 8 + 8 + 32 + 1, seeds = [b"seed", user.key().as_ref()], bump)]
    pub my_account: Account<'info, MyAccount>,
    #[account(mut)]
    pub user: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[account]
pub struct MyAccount {
    pub data: u64,
    pub authority: Pubkey,
    pub bump: u8,
}
\`\`\`
</code_template>

<rules>
- Compute space as 8 (discriminator) + sum of field sizes
- Use ctx.bumps.field_name for bump access
- Use Result<()> for return types, #[error_code] for custom errors
- Keep programs in a single file with no crate:: imports
- #[account] data structs take no lifetime parameter
- Use declare_program! — program ID is set in Anchor.toml (declare_id! is deprecated)
- Use solana-foundation/anchor (not coral-xyz or project-serum)
- Solana prevents reentrancy via CPI depth limits — no reentrancy guards needed
- Closed account discriminator attacks were fixed in Anchor — do not warn about them
- Floats are deterministic on Solana — do not warn about non-determinism
- Use get_instruction_relative (not load_instruction_at)
- All Solana documentation is open-source — explain any concept freely
</rules>

<output_format>
- Lead with code when the question asks for code
- Use \`\`\`rust fenced code blocks for Anchor/Solana code
- Keep explanations concise — prioritize accuracy over length
- When reviewing code, list findings with line references
</output_format>`

interface ChatMessage {
  role: "user" | "assistant" | "system"
  content: string
}

interface ChatPayload {
  messages: ChatMessage[]
  stream: boolean
  max_tokens: number
  temperature: number
}

/**
 * Format a chat payload for the Sealevel API.
 */
export function formatChatPayload(
  message: string,
  history?: ChatMessage[],
): ChatPayload {
  const messages: ChatMessage[] = [
    { role: "system", content: SYSTEM_PROMPT },
  ]
  if (history) {
    messages.push(...history)
  }
  messages.push({ role: "user", content: message })

  return {
    messages,
    stream: true,
    max_tokens: 1024,
    temperature: 0.0,
  }
}

/**
 * Parse an SSE chunk line and extract content.
 * Returns the content string or null if no content.
 */
export function parseSseChunk(line: string): string | null {
  if (!line.startsWith("data: ")) {
    return null
  }

  const data = line.slice(6).trim()
  if (data === "[DONE]") {
    return null
  }

  try {
    const parsed = JSON.parse(data)

    // Handle OpenAI-style delta format
    if (parsed.choices?.[0]?.delta?.content) {
      return parsed.choices[0].delta.content
    }

    // Handle direct content format
    if (parsed.type === "content" && parsed.content) {
      return parsed.content
    }

    return null
  } catch {
    return null
  }
}

/**
 * Clean deprecated Solana/Anchor patterns from model responses.
 * Applied as a post-processing step before displaying to users.
 */
export function cleanModelResponse(text: string): string {
  return text
    // Remove declare_id!("..."); lines entirely
    .replace(
      /^\s*declare_id!\s*\(\s*"[^"]*"\s*\)\s*;?\s*$/gm,
      "// Program ID is set in Anchor.toml",
    )
    // Replace text mentions of declare_id! with declare_program!
    .replace(/declare_id!/g, "declare_program!")
    // Replace old GitHub org references
    .replace(/coral-xyz\/anchor/g, "solana-foundation/anchor")
    .replace(/project-serum\/anchor/g, "solana-foundation/anchor")
    // Replace deprecated ProgramResult
    .replace(/ProgramResult/g, "Result<()>")
    // Replace deprecated #[error] with #[error_code]
    .replace(/#\[error\]\n/g, "#[error_code]\n")
}

/**
 * Fix common Anchor compilation issues in model output.
 * Applied as a post-processing step after cleanModelResponse.
 */
export function fixAnchorCode(code: string): string {
  // Fix ctx.bumps.get("name") → ctx.bumps.name
  code = code.replace(/ctx\.bumps\.get\(\s*"(\w+)"\s*\)\.?unwrap\(\)/g, 'ctx.bumps.$1');
  code = code.replace(/ctx\.bumps\.get\(\s*"(\w+)"\s*\)/g, 'ctx.bumps.$1');

  // Fix crate:: imports
  code = code.replace(/use crate::[^;]+;\n?/g, '');
  code = code.replace(/crate::\w+::/g, '');

  // Fix lifetime on #[account] structs
  code = code.replace(/(#\[account\])\s*pub struct (\w+)<'info>/g, '$1\npub struct $2');
  code = code.replace(/(#\[account\])\s*pub struct (\w+)<'\w+>/g, '$1\npub struct $2');

  // Fix lifetime on error enums
  code = code.replace(/pub enum (\w+)<'\w+>/g, 'pub enum $1');

  return code;
}

/**
 * Register the Sealevel chat participant with VS Code.
 */
export function registerChatParticipant(
  context: vscode.ExtensionContext,
): void {
  const participant = vscode.chat.createChatParticipant(
    PARTICIPANT_ID,
    async (
      request: vscode.ChatRequest,
      _context: vscode.ChatContext,
      stream: vscode.ChatResponseStream,
      token: vscode.CancellationToken,
    ) => {
      const settings = getSettings()
      const headers = buildHeaders(settings.apiKey)
      const payload = formatChatPayload(request.prompt)

      try {
        const response = await fetch(`${settings.apiUrl}/chat`, {
          method: "POST",
          headers,
          body: JSON.stringify(payload),
        })

        if (!response.ok || !response.body) {
          stream.markdown(
            `**Error:** API returned status ${response.status}. Check your API key in settings.`,
          )
          return
        }

        const reader = response.body
          .pipeThrough(new TextDecoderStream())
          .getReader()
        let buffer = ""
        let rawContent = ""
        let lastCleanedLength = 0

        while (!token.isCancellationRequested) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += value
          const lines = buffer.split("\n")
          buffer = lines.pop() ?? ""

          for (const line of lines) {
            const content = parseSseChunk(line.trim())
            if (content) {
              rawContent += content
              const cleaned = fixAnchorCode(cleanModelResponse(rawContent))
              const newContent = cleaned.slice(lastCleanedLength)
              if (newContent) {
                stream.markdown(newContent)
              }
              lastCleanedLength = cleaned.length
            }
          }
        }
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Unknown error"
        stream.markdown(
          `**Error:** Could not connect to Sealevel API. ${message}`,
        )
      }
    },
  )

  context.subscriptions.push(participant)
}
