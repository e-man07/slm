# Component Library & Design System

## Design Tokens

### Theme
- Style: `radix-maia`
- Base color: `olive` (oklch green-grey tones)
- Border radius: `0` (sharp corners, terminal aesthetic)
- Dark mode: default via `next-themes`

### Typography
- **Primary (mono)**: JetBrains Mono — headings, body, code (global `font-mono`)
- **Sans fallback**: Geist — used sparingly where mono feels wrong
- Decision: monospace everywhere reinforces the developer-tool identity

### Colors (Dark Mode)
| Token | Value | Use |
|-------|-------|-----|
| `--background` | `oklch(0.153 0.006 107.1)` | Page background |
| `--foreground` | `oklch(0.988 0.003 106.5)` | Primary text |
| `--card` | `oklch(0.228 0.013 107.4)` | Card surfaces |
| `--primary` | `oklch(0.93 0.007 106.5)` | Buttons, links |
| `--muted-foreground` | `oklch(0.737 0.021 106.9)` | Secondary text |
| `--border` | `oklch(1 0 0 / 10%)` | Borders |
| `--destructive` | `oklch(0.704 0.191 22.216)` | Errors |
| `--chart-1` through `--chart-5` | Green gradient | Eval charts |

---

## shadcn/ui Components to Install

```bash
cd slm-web

# Core
npx shadcn@latest add input textarea card badge tabs

# Data display
npx shadcn@latest add table accordion separator

# Feedback
npx shadcn@latest add toast tooltip skeleton

# Navigation
npx shadcn@latest add dropdown-menu scroll-area

# Forms
npx shadcn@latest add switch dialog

# Chat-specific
npx shadcn@latest add avatar command
```

---

## Custom Components

### Layout

**`NavBar`** (`components/nav-bar.tsx`)
- Logo (SLM wordmark)
- Page links: Chat, Explain, Docs, Eval
- Theme toggle (dark/light)
- GitHub link (icon)
- API key status indicator (if logged in)

**`Footer`** (`components/footer.tsx`)
- Minimal: GitHub, Docs, Built for Solana
- Not shown on /chat page

**`PageLayout`** (`components/shared/page-layout.tsx`)
- Wraps NavBar + content + Footer
- Max-width container with padding
- Used on all pages except /chat

### Chat Components

**`ChatMessage`** (`components/chat/chat-message.tsx`)
- Props: `role`, `content`, `isStreaming`
- User messages: right-aligned, primary background
- Assistant messages: left-aligned, card background
- Renders markdown with syntax highlighting
- Copy button on hover
- Feedback buttons (thumbs up/down) on assistant messages

**`ChatInput`** (`components/chat/chat-input.tsx`)
- Textarea with auto-resize
- Send button (disabled when empty)
- Cmd+Enter keyboard shortcut
- Character count (subtle)

**`StreamingText`** (`components/chat/streaming-text.tsx`)
- Props: `text`, `isComplete`
- Renders text token-by-token
- Blinking cursor at the end while streaming
- Transitions to static text when complete

**`CodeBlock`** (`components/shared/code-block.tsx`)
- Props: `code`, `language`, `filename?`
- Syntax highlighting (use `shiki` or `prism-react-renderer`)
- Language label badge (top-right)
- Copy button
- Line numbers (optional)

### Explain Components

**`TxSignatureInput`** (`components/explain/tx-signature-input.tsx`)
- Single-line input with base58 validation
- Paste button (clipboard icon)
- "Try example" link
- Submit button

**`TxResult`** (`components/explain/tx-result.tsx`)
- Props: `txData`, `explanation`, `isStreaming`
- Structured data section (status badge, type, fee, instructions table)
- AI explanation section (streaming text below)

**`ErrorCodeInput`** (`components/explain/error-code-input.tsx`)
- Two inputs: error code (hex/decimal) + program ID (optional)
- Decode button
- Popular errors as quick-select pills

**`ErrorResult`** (`components/explain/error-result.tsx`)
- Props: `lookupResult`, `explanation`, `isStreaming`
- Lookup card (program name, error name, message)
- AI explanation section (streaming text below)

### Eval Components

**`EvalScoreHero`** (`components/eval/eval-score-hero.tsx`)
- Large percentage display (87.5%)
- Subtitle: "70 of 80 tasks passed"
- Pass/fail color coding

**`EvalCategoryChart`** (`components/eval/eval-category-chart.tsx`)
- Horizontal bar chart
- 7 categories with pass rates
- Uses `--chart-*` CSS variables
- Build with div widths (no charting library needed for MVP)

**`EvalTaskTable`** (`components/eval/eval-task-table.tsx`)
- Accordion per category
- Individual tasks with pass/fail badge
- Expandable to show task prompt

### Dashboard Components

**`ApiKeyDisplay`** (`components/dashboard/api-key-display.tsx`)
- Masked key: `slm_xxxx...xxxx`
- Copy button
- Regenerate button (with confirmation dialog)

---

## Hooks

**`useChat`** (`hooks/use-chat.ts`)
- State: messages array, isLoading, error
- Actions: sendMessage, clearChat
- Handles SSE streaming internally
- Returns: `{ messages, sendMessage, clearChat, isLoading, error }`

**`useStreaming`** (`hooks/use-streaming.ts`)
- Low-level SSE hook
- Props: endpoint URL, request body
- Returns: `{ data, isStreaming, error, start, stop }`
- Handles `fetch` with `ReadableStream` for SSE parsing

**`useApiKey`** (`hooks/use-api-key.ts`)
- State: API key from localStorage
- Actions: setKey, clearKey
- Auto-attaches to requests via header

---

## Utilities

**`lib/constants.ts`**
- `SYSTEM_PROMPT` — the 6-rule Solana guardrail prompt
- `API_URL` — SGLang endpoint
- `HELIUS_API_URL` — Helius base URL

**`lib/sse.ts`**
- `parseSSEStream(response)` — async generator yielding parsed SSE events
- Handles `data: [DONE]` termination

**`lib/api-client.ts`**
- `chatCompletions(messages, options)` — typed fetch wrapper
- `explainTransaction(signature)` — typed fetch wrapper
- `decodeError(code, programId?)` — typed fetch wrapper

**`lib/errors.ts`**
- `lookupError(code, programId?)` — searches static error table
- Returns `{ programName, errorName, errorMessage, code, hex }`

**`lib/helius.ts`**
- `fetchEnhancedTransaction(signature)` — Helius API client
- Returns parsed transaction data
