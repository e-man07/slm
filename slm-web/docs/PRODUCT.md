# Sealevel Product Spec

## What is Sealevel?

Sealevel (Solana Language Model) is a Solana-specialized coding assistant. It's a fine-tuned Qwen2.5-Coder-7B-Instruct model that scores 87.5% on 80 Solana-specific coding tasks, served through multiple interfaces: web chat, transaction explainer, error decoder, Python CLI, and VS Code extension.

## Target Users

- Solana/Anchor developers (beginners to experienced)
- DeFi protocol teams building on Solana
- Hackathon participants writing Anchor programs
- Anyone debugging Solana transactions or errors

## Core Value Props

1. **Solana-specific accuracy** - 93-100% on PDA derivation, Anchor constraints, SPL token ops, transaction construction
2. **Transaction explanation** - Paste a tx signature, get human-readable breakdown via Helius
3. **Error decoding** - 1,914 known errors from 41 Solana programs, decoded instantly
4. **Everywhere you code** - Web, VS Code, CLI, API, or run locally via Ollama

## Product Surfaces

| Surface | Access | Auth Required |
|---------|--------|---------------|
| Web Chat (`/chat`) | Browser | No (anonymous tier) |
| Tx Explainer (`/explain/tx`) | Browser | No |
| Error Decoder (`/explain/error`) | Browser | No |
| API (`/api/*`) | HTTP | Yes (API key) |
| Python CLI (`slm-cli`) | Terminal | Yes (API key) |
| VS Code Extension | Editor | No (anonymous), Yes (standard) |
| Ollama (local) | Terminal | No (runs locally) |

## Rate Limit Tiers

| Tier | Requests/min | Tokens/day | Access |
|------|-------------|-----------|--------|
| Anonymous | 5 | 10K | No signup |
| Free | 10 | 50K | GitHub OAuth |
| Standard | 30 | 500K | Applied |
| Admin | 100 | Unlimited | Team |

## Model Details

- **Base**: Qwen2.5-Coder-7B-Instruct (7B dense)
- **Training**: QLoRA SFT on 10K curated Solana instruction pairs
- **Eval**: 87.5% (70/80) on custom Solana benchmark
- **Serving**: SGLang on Akash A100/H100
- **Local**: GGUF Q3_K_M via Ollama (fits 16GB RAM)

## System Prompt Guardrails

The model is instructed to:
1. Never use `declare_id!` (use `declare_program!`)
2. Never suggest reentrancy guards (Solana prevents reentrancy via CPI depth limits)
3. Never reference `coral-xyz/anchor` (use `solana-foundation/anchor`)
4. Never warn about closed account discriminator attacks (fixed years ago)
5. Never suggest float non-determinism concerns (deterministic on Solana)
6. Never use `load_instruction_at` (use `get_instruction_relative`)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, Tailwind v4 |
| Components | shadcn/ui (radix-maia, olive, zero radius) |
| Fonts | JetBrains Mono (primary), Geist (sans) |
| Icons | Hugeicons |
| Theme | next-themes (dark mode default) |
| Inference | SGLang on Akash |
| Tx Parsing | Helius Enhanced Transaction API |
| Error Lookup | Static JSON (41 programs, 1,914 errors) |
| CLI | Python: typer + httpx + rich |
| VS Code | Chat Participant API |
