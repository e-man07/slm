# Page Specifications

## 1. Landing Page (`/`)

### Sections
1. **Hero** - "SLM" wordmark, tagline: "The Solana coding AI that actually knows Solana", two CTAs: "Try it" → /chat, "Get API key" → /dashboard
2. **Features Grid** - 4 cards: Chat, Tx Explainer, Error Decoder, API Access. Each with Hugeicon, title, one-line description, link
3. **Install** - Tabbed code blocks showing: CLI (`pip install slm-cli`), VS Code (marketplace link), API (curl example), Ollama (`ollama run slm-solana`)
4. **Eval Results** - Summary bar showing 87.5% overall with category breakdown. Link to /eval
5. **Footer** - GitHub, docs, Solana Foundation attribution

### Design Notes
- Dark mode default
- Full-width sections, single column
- Sharp corners (radius: 0) throughout
- Monospace headings (JetBrains Mono)

---

## 2. Chat (`/chat`)

### Layout
- Full viewport height, no footer
- NavBar at top (minimal: logo + back to home + theme toggle)
- Message list: scrollable, auto-scroll on new messages
- Input area: fixed bottom, textarea + send button

### Components
- `ChatMessage` - User (right-aligned bg) vs Assistant (left-aligned). Markdown rendered with syntax highlighting for code blocks
- `StreamingText` - Token-by-token rendering with blinking cursor
- `ChatInput` - Textarea, Cmd+Enter to send, character count

### States
- **Empty**: 3-4 suggested prompts as clickable pills
  - "How do I create a PDA in Anchor?"
  - "Write an SPL token transfer"
  - "Explain error 0x1771"
  - "Review my Anchor code for security issues"
- **Loading**: Typing indicator (three dots or skeleton)
- **Streaming**: Tokens appear one by one with cursor
- **Error**: Toast notification (rate limited, connection lost, model unavailable)

### Behavior
- Conversation stored in client state (no backend persistence for MVP)
- "New chat" button clears history
- Each assistant message has copy button + feedback (thumbs up/down)
- Code blocks have copy button + language label

---

## 3. Transaction Explainer (`/explain/tx`)

### Layout
- NavBar + PageLayout
- Input section (top): single-line input for tx signature, "Explain" button
- Result section (below): two parts

### Input
- Text input with placeholder: "Paste a Solana transaction signature..."
- Paste button (clipboard icon)
- Example link: "Try this example" (pre-fills a known tx)
- Client-side validation: base58, 87-88 chars

### Result Display
- **Structured data** (appears first, from Helius):
  - Status badge: Success/Failed
  - Type: e.g., "SWAP", "TRANSFER", "NFT_MINT"
  - Fee: in SOL
  - Block / Timestamp
  - Instructions list (collapsible)
  - Token transfers table (if any)
- **AI Explanation** (streams below):
  - Natural language explanation of what the transaction did
  - Streamed via SSE

### States
- **Empty**: Input focused, example link visible
- **Loading**: Skeleton for structured data, then streaming for AI explanation
- **Error**: Invalid signature, tx not found, Helius rate limited

---

## 4. Error Decoder (`/explain/error`)

### Layout
- NavBar + PageLayout
- Input section: two fields side by side
- Result section below

### Input
- Error code: text input, accepts hex (0x1771) or decimal (6001)
- Program ID: text input (optional), placeholder "Program ID (optional)"
- "Decode" button

### Result Display
- **Lookup result** (instant):
  - Program name + icon
  - Error name (e.g., "InsufficientFunds")
  - Error message (e.g., "Insufficient funds for this operation")
  - Error code (hex + decimal)
- **AI Explanation** (streams below):
  - What causes this error
  - How to fix it
  - Code example showing the fix

### States
- **Empty**: Popular errors as quick links (ConstraintMut 2000, AccountNotInitialized 3012, etc.)
- **Found**: Structured result + AI explanation
- **Not Found**: "Error not found in 41 known programs" + AI best-effort explanation
- **Error**: Invalid format

---

## 5. API Docs (`/docs`)

### Layout
- NavBar + sidebar navigation + content area
- Sidebar: section links (Auth, Chat, Tx Explainer, Error Decoder, Rate Limits, SDKs)
- Content: markdown-rendered documentation

### Sections
1. **Authentication**: API key header format, how to get a key
2. **Chat Completions**: POST /api/chat, request/response, streaming example
3. **Transaction Explainer**: POST /api/explain/tx, request/response
4. **Error Decoder**: POST /api/explain/error, request/response
5. **Rate Limits**: Tier table, headers returned
6. **SDK Examples**: Python (httpx), TypeScript (fetch), curl
7. **Error Codes**: Standard error response format

### Design Notes
- Code blocks with copy buttons
- Request/response examples side by side or tabbed
- Try-it-out buttons that open the web chat with pre-filled prompts

---

## 6. Eval Dashboard (`/eval`)

### Layout
- NavBar + PageLayout
- Overall score hero (87.5%)
- Category breakdown chart
- Individual task results table

### Components
- **Score Hero**: Large "87.5%" with "70 of 80 tasks passed" subtitle
- **Category Chart**: Horizontal bar chart showing pass rate per category
- **Results Table**: Category (expandable) → individual tasks with pass/fail badge

### Data
- Static JSON imported at build time from `data/eval-results.json`
- No live evaluation — updated when model is retrained

### Categories
| Category | Tasks | Pass Rate |
|----------|-------|-----------|
| PDA Derivation | 15 | 93% |
| Anchor Constraints | 15 | 100% |
| SPL Token Operations | 10 | 100% |
| CPI Invocation | 10 | ~90% |
| Error Handling | 10 | ~90% |
| Adversarial | 10 | 30% |
| Transaction Construction | 10 | ~100% |

---

## 7. Dashboard (`/dashboard`)

### Layout
- Requires GitHub OAuth login
- NavBar + PageLayout
- API key section + usage stats

### Components
- **API Key Card**: Masked key display, copy button, regenerate button
- **Usage Stats**: Requests today, tokens used, simple daily chart
- **Tier Info**: Current tier badge, what's included

### MVP Scope
- Simple key display + copy
- Basic usage counter
- No payment/upgrade flow (manual tier assignment)
