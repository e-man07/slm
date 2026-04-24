# API Specifications

## Base URL
- Production: `https://www.sealevel.tech/api`
- Local: `http://localhost:3000/api`

## Authentication
All API routes require an `Authorization` header:
```
Authorization: Bearer slm_xxxxxxxxxxxx
```
Without auth, requests return 401. Get a key at [sealevel.tech/dashboard](/dashboard) or via `slm login`.

---

## POST /api/chat

Stream or non-stream chat completions. OpenAI-compatible format.

### Request
```json
{
  "messages": [
    {"role": "user", "content": "How do I create a PDA in Anchor?"}
  ],
  "stream": true,
  "max_tokens": 4096,
  "temperature": 0.0
}
```

### Response (stream: true)
SSE format, OpenAI-compatible:
```
data: {"choices":[{"delta":{"role":"assistant"},"index":0}]}

data: {"choices":[{"delta":{"content":"In"},"index":0}]}

data: {"choices":[{"delta":{"content":" Anchor"},"index":0}]}

data: [DONE]
```

### Response (stream: false)
```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "In Anchor 0.30+, you derive a PDA using seeds..."
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 45,
    "completion_tokens": 312,
    "total_tokens": 357
  }
}
```

### Behavior
- System prompt with 6 Solana guardrails is injected server-side
- Messages are forwarded to SGLang at the inference endpoint
- Conversation history is passed as-is from the client

---

## POST /api/explain/tx

Explain a Solana transaction in human-readable format.

### Request
```json
{
  "signature": "5UfDuX7WXYxjng1PYLJmzGRqaWEd7dMN5Ld5sgsMUPoStSK7F4EzPbf..."
}
```

### Response (SSE stream)
First event contains structured transaction data:
```
data: {"type":"tx_data","data":{"status":"success","type":"SWAP","fee":0.000005,"feePayer":"9WzD...","blockTime":1712345678,"instructions":[...],"tokenTransfers":[...]}}

data: {"type":"content","content":"This transaction"}

data: {"type":"content","content":" performs a token swap"}

data: [DONE]
```

### Fields in tx_data
| Field | Type | Description |
|-------|------|-------------|
| status | string | "success" or "failed" |
| type | string | Transaction type from Helius (SWAP, TRANSFER, etc.) |
| fee | number | Fee in SOL |
| feePayer | string | Fee payer public key |
| blockTime | number | Unix timestamp |
| instructions | array | Parsed instruction list |
| tokenTransfers | array | Token transfer details |

---

## POST /api/explain/error

Decode a Solana program error code.

### Request
```json
{
  "error_code": "0x1771",
  "program_id": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
}
```

### Response (SSE stream)
First event contains static lookup result:
```
data: {"type":"lookup","data":{"program_name":"SPL Token","error_name":"InsufficientFunds","error_message":"Insufficient funds","code":6001,"hex":"0x1771"}}

data: {"type":"content","content":"This error occurs when"}

data: {"type":"content","content":" the token account doesn't have enough"}

data: [DONE]
```

If error not found in lookup table:
```
data: {"type":"lookup","data":null}

data: {"type":"content","content":"I'll try to explain this error..."}
```

---

## GET /api/health

### Response
```json
{
  "status": "ok",
  "sglang": true,
  "timestamp": "2026-04-05T12:00:00Z"
}
```

Possible status values: `ok`, `degraded` (inference slow), `down` (inference unreachable).

---

## Error Responses

All routes return errors in this format:
```json
{
  "error": {
    "code": "rate_limited",
    "message": "Rate limit exceeded. Upgrade at sealevel.tech/dashboard",
    "status": 429
  }
}
```

### Error Codes
| Code | Status | Description |
|------|--------|-------------|
| `unauthorized` | 401 | Invalid or missing API key |
| `rate_limited` | 429 | Rate limit exceeded |
| `invalid_input` | 400 | Bad request format |
| `model_unavailable` | 503 | SGLang is unreachable |
| `upstream_timeout` | 504 | SGLang took too long |
| `tx_not_found` | 404 | Transaction signature not found |
| `helius_error` | 502 | Helius API failure |

### Rate Limit Headers
```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1712345678
```
