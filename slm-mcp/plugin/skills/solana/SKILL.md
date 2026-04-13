# SLM - Solana Language Model

Expert Solana and Anchor development assistant powered by a fine-tuned language model (87.5% eval score).

## Available Tools

### slm_chat
Ask SLM any question about Solana or Anchor development. Provides accurate, up-to-date guidance using modern Anchor 0.30+ patterns.

### slm_decode_error
Look up any Solana or Anchor error code (decimal or hex). Returns the program name, error name, and human-readable message. Works offline with a bundled error table covering 324+ errors.

### slm_explain_tx
Explain what a Solana transaction did by providing its signature. Returns structured transaction data and a plain-English explanation.

### slm_review_code
Review Solana/Anchor code for deprecated patterns and common mistakes. Checks for 6 known anti-patterns including deprecated declare_id!, coral-xyz/anchor references, unnecessary reentrancy guards, and more.

### slm_migrate_code
Automatically migrate old Solana/Anchor code to modern Anchor 0.30+ patterns. Handles declare_id! to declare_program!, InitSpace, ctx.bumps, and more.

## Resources

- `solana://errors` - Complete Solana/Anchor error table
- `solana://eval-results` - SLM model evaluation results
- `solana://system-prompt` - SLM guardrail rules

## Prompts

- `solana-expert` - General Solana dev assistance (arg: topic)
- `anchor-migration` - Migrate old Anchor code (arg: code)
- `security-review` - Security audit of Anchor code (arg: code)

## Configuration

Set `SLM_API_KEY` environment variable for authenticated access to the SLM API. The decode error and review code tools work fully offline.
