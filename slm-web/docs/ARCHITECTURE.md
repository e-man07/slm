# System Architecture

## High-Level Diagram

```
Browser / CLI / VS Code
        |
   Next.js App (Vercel)
   ├── /api/chat          ──> SGLang (Akash GPU)
   ├── /api/explain/tx    ──> Helius API ──> SGLang
   ├── /api/explain/error ──> Static Lookup ──> SGLang
   └── /api/auth          ──> SQLite (API keys)
```

## Request Flows

### Chat (`POST /api/chat`)
```
User message
  → Next.js API route
  → Inject system prompt (6 guardrails)
  → Forward to SGLang (/v1/chat/completions)
  → Stream SSE back to client
```

### Transaction Explainer (`POST /api/explain/tx`)
```
Tx signature
  → Next.js API route
  → Helius Enhanced Transaction API (100 credits/call)
  → Parse: type, instructions, token transfers, fees
  → Build prompt with parsed data
  → SGLang streaming explanation
  → SSE back to client
```

### Error Decoder (`POST /api/explain/error`)
```
Error code + program ID
  → Next.js API route
  → Static lookup: error-table.json (1,914 errors, 41 programs)
  → If found: error name + message
  → Build prompt with error context
  → SGLang streaming explanation
  → SSE back to client
```

## Infrastructure

### GPU Instance (Akash)
- SGLang serving merged model or base + LoRA
- A100 80GB or RTX 4090 24GB (AWQ 4-bit)
- Port 30000 (internal)
- Cost: ~$1.27/hr (A100) or ~$0.40/hr (4090)

### Frontend (Vercel or self-hosted)
- Next.js 16 with API routes
- API routes proxy to SGLang
- Static assets: eval results, error lookup table

### External Services
- **Helius**: Transaction parsing (free tier: 10K calls/month)
- **GitHub OAuth**: User authentication for API keys

## Latency Budget

| Component | Target |
|-----------|--------|
| System prompt injection | <1ms |
| SGLang TTFT | 50-200ms |
| Token generation | 40-80 tok/s |
| Helius API call | 200-500ms |
| Error table lookup | <1ms |
| **Total TTFT (chat)** | **<300ms** |
| **Total TTFT (tx explain)** | **<700ms** |

## Context Window Budget (32K effective)

| Allocation | Tokens |
|-----------|--------|
| System prompt | 500 |
| Conversation history | 8,000 |
| User message | 4,000 |
| Generation headroom | 19,500 |
| **Total** | **32,000** |

## Fallback Strategy

1. SGLang timeout (5s) → return error with suggestion to retry
2. Helius API failure → return "unable to fetch transaction"
3. Error not in lookup table → LLM attempts explanation from code alone
4. API unavailable → VS Code/CLI fallback to local Ollama if configured
