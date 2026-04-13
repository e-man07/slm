# Data Contracts & Static Assets

## System Prompt

Used across ALL surfaces (web, CLI, VS Code, API). Must be identical everywhere.

```
You are SLM, an expert Solana and Anchor development assistant.
Provide accurate, secure, and up-to-date code using modern Anchor 0.30+ patterns
(solana-foundation/anchor, InitSpace, ctx.bumps.field_name).
When uncertain, say so rather than guessing.
Never suggest reentrancy guards (Solana prevents reentrancy via CPI depth limits).
Never reference coral-xyz/anchor or declare_id! - these are deprecated.
Never warn about closed account discriminator attacks (fixed in Anchor years ago).
Never suggest float non-determinism concerns (deterministic on Solana).
Never use load_instruction_at (use get_instruction_relative instead).
```

Stored in: `lib/constants.ts` as `SYSTEM_PROMPT`

---

## Eval Results Schema

File: `data/eval-results.json`
Source: Copy from `../../results/phase1/eval_results.json`

```typescript
interface EvalResults {
  model: string
  checkpoint: string
  timestamp: string
  overall: {
    total: number
    passed: number
    failed: number
    pass_rate: number
  }
  categories: {
    name: string
    tasks: number
    passed: number
    failed: number
    pass_rate: number
  }[]
  tasks: {
    id: string
    category: string
    prompt: string
    passed: boolean
    time_seconds: number
    patterns_matched?: string[]
    fail_reason?: string
  }[]
}
```

---

## Error Lookup Table Schema

File: `data/error-table.json`
Source: Generated from Anchor IDLs (41 programs, 1,914 errors)

```typescript
interface ErrorTable {
  programs: {
    program_id: string
    program_name: string
    errors: {
      code: number
      hex: string
      name: string
      message: string
    }[]
  }[]
}
```

### Common Anchor Framework Errors (built-in)

| Code | Hex | Name | Message |
|------|-----|------|---------|
| 100 | 0x64 | InstructionMissing | 8 byte instruction identifier not provided |
| 101 | 0x65 | InstructionFallbackNotFound | Fallback functions are not supported |
| 2000 | 0x7D0 | ConstraintMut | A mut constraint was violated |
| 2001 | 0x7D1 | ConstraintHasOne | A has one constraint was violated |
| 2003 | 0x7D3 | ConstraintSeeds | A seeds constraint was violated |
| 2006 | 0x7D6 | ConstraintOwner | An owner constraint was violated |
| 2012 | 0x7DC | ConstraintSpace | A space constraint was violated |
| 3000 | 0xBB8 | AccountDiscriminatorAlreadySet | The account discriminator was already set |
| 3012 | 0xBC4 | AccountNotInitialized | The program expected this account to be already initialized |

Custom program errors start at 6000. Subtract 6000 to get the variant index in the program's error enum.

---

## Chat Message Schema (Client-Side)

```typescript
interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: number
  isStreaming?: boolean
  feedback?: "up" | "down"
}
```

---

## Helius Enhanced Transaction Response (Subset Used)

```typescript
interface HeliusTxData {
  description: string
  type: string // "SWAP", "TRANSFER", "NFT_MINT", etc.
  fee: number
  feePayer: string
  signature: string
  slot: number
  timestamp: number
  nativeTransfers: {
    fromUserAccount: string
    toUserAccount: string
    amount: number
  }[]
  tokenTransfers: {
    fromUserAccount: string
    toUserAccount: string
    fromTokenAccount: string
    toTokenAccount: string
    tokenAmount: number
    mint: string
    tokenStandard: string
  }[]
  instructions: {
    programId: string
    data: string
    accounts: string[]
    innerInstructions: any[]
  }[]
}
```

---

## Static Assets Needed

| Asset | Location | Description |
|-------|----------|-------------|
| `logo.svg` | `public/logo.svg` | SLM wordmark for NavBar |
| `og-image.png` | `public/og-image.png` | 1200x630 social preview |
| `favicon.ico` | `app/favicon.ico` | Already exists |
