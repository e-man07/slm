# Implementation Order

## Phase A: Foundation (Day 1-2)

### A1. Install shadcn/ui components
```bash
npx shadcn@latest add input textarea card badge tabs table accordion toast tooltip skeleton separator scroll-area switch dialog dropdown-menu avatar command
```

### A2. Build layout components
- `components/nav-bar.tsx`
- `components/footer.tsx`
- `components/shared/page-layout.tsx`

### A3. Build shared utilities
- `lib/constants.ts` — system prompt, API URLs
- `lib/sse.ts` — SSE stream parser
- `lib/api-client.ts` — typed fetch helpers

### A4. Build shared components
- `components/shared/code-block.tsx` — syntax highlighting with copy button

---

## Phase B: Chat (Day 2-4) — Highest demo value

### B1. API route
- `app/api/chat/route.ts` — proxy to SGLang with system prompt injection, SSE streaming

### B2. Hooks
- `hooks/use-streaming.ts` — low-level SSE hook
- `hooks/use-chat.ts` — chat state management

### B3. Components
- `components/chat/chat-message.tsx`
- `components/chat/chat-input.tsx`
- `components/chat/streaming-text.tsx`

### B4. Page
- `app/chat/page.tsx` — full-height chat interface with suggested prompts

---

## Phase C: Explainers (Day 4-6)

### C1. Data
- `data/error-table.json` — static error lookup table
- `lib/errors.ts` — error lookup function
- `lib/helius.ts` — Helius API client

### C2. API routes
- `app/api/explain/tx/route.ts`
- `app/api/explain/error/route.ts`

### C3. Components
- `components/explain/tx-signature-input.tsx`
- `components/explain/tx-result.tsx`
- `components/explain/error-code-input.tsx`
- `components/explain/error-result.tsx`

### C4. Pages
- `app/explain/tx/page.tsx`
- `app/explain/error/page.tsx`

---

## Phase D: Landing + Eval (Day 6-7)

### D1. Data
- `data/eval-results.json` — copy from `results/phase1/eval_results.json`

### D2. Eval components
- `components/eval/eval-score-hero.tsx`
- `components/eval/eval-category-chart.tsx`
- `components/eval/eval-task-table.tsx`

### D3. Pages
- `app/eval/page.tsx`
- `app/page.tsx` — landing page (hero, features, install, eval embed)

---

## Phase E: Dashboard + Auth (Day 7-9) — Can defer

### E1. Auth
- GitHub OAuth (NextAuth.js or Clerk)
- API key generation + storage

### E2. Components
- `components/dashboard/api-key-display.tsx`

### E3. Page
- `app/dashboard/page.tsx`

---

## Phase F: API Docs (Day 9-10)

### F1. Page
- `app/docs/page.tsx` — rendered markdown or MDX

---

## Phase G: External Clients (Day 10-14) — Parallel workstream

### G1. Python CLI
- Separate repo or `packages/slm-cli/`
- typer + httpx + rich
- ~200-300 lines

### G2. VS Code Extension
- Separate repo or `packages/slm-vscode/`
- Chat Participant API
- ~150 lines TypeScript

---

## Hackathon MVP Scope

**Must have** (Phases A-D):
- Working chat with streaming
- Transaction explainer
- Error decoder
- Landing page with eval results

**Nice to have** (Phase E-G):
- Dashboard with API keys
- API docs page
- Python CLI
- VS Code extension

---

## Dependencies

```
A (Foundation) → B (Chat) → C (Explainers) → D (Landing + Eval)
                                              ↓
                                        E (Dashboard) → F (Docs)
                                              ↓
                                        G (External Clients)
```

B, C, D must be sequential. E, F, G can be parallel after D.

---

## Infrastructure (Parallel Track)

While building the web app:
1. Re-run Phase 1 SFT training (~1.5 hours)
2. Export merged model for SGLang
3. Deploy SGLang on Akash
4. Sign up for Helius free tier
5. Set up domain (slm.dev or similar)
