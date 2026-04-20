# Sealevel Production Readiness Audit

**Date:** April 17, 2026
**Scope:** All 5 components — Web App, Deploy/Infra, CLI, MCP Server, VS Code Extension

---

## Executive Summary

**Verdict: ~70% production-ready.**

Strong foundation — auth, rate limiting, DB schema, multi-client architecture all solid. But **critical security gaps** and missing operational pieces block a safe public launch.

| Area | Readiness |
|------|-----------|
| Core functionality | Ready |
| Auth & access control | Ready |
| Rate limiting | Ready |
| Security hardening | **Not ready** |
| Operational maturity | **Not ready** |
| Documentation | Ready |
| RFP alignment | 80% — gaps in adversarial robustness and roadmap |

---

## Solana Foundation RFP Fit Analysis

Based on the [Solana Foundation Sealevel RFP](https://forum.solana.com/t/request-for-proposal-rfp-solana-language-model/4631).

| RFP Requirement | Status | Notes |
|---|---|---|
| Fine-tuned LLM or hybrid approach | **Covered** | Qwen2.5-Coder-7B-Instruct + QLoRA + RAG |
| Solana-specific training data | **Covered** | 731K SFT records from curated ecosystem sources |
| Latency compatible with Solana throughput | **Covered** | SGLang on H100, streaming responses |
| Scalability strategy | **Partial** | LiteLLM proxy + rate limiting, but no multi-GPU / auto-scaling story |
| Cost efficiency at scale | **Covered** | 7B dense model, $10K budget, Akash credits |
| Hallucination mitigation | **Partial** | RAG for up-to-date docs, system prompt guardrails, logit bias — but adversarial score only 40% |
| Adversarial robustness | **Gap** | 40% adversarial score. DPO planned but not yet run |
| Auditability of model behavior | **Covered** | Eval benchmarks (85%), MODEL_CARD.md |
| Output verification / constraining | **Partial** | Deprecated pattern detection in VS Code/MCP, no formal verification |
| Anchor integration | **Covered** | Modern Anchor 0.30+ patterns, migration tool |
| Solana CLI integration | **Covered** | CLI tool with tx explainer + error decoder |
| Developer workflow integration | **Strong** | VS Code + CLI + MCP + Web — 4 interfaces |
| System architecture doc | **Covered** | README + deploy docs + MODEL_CARD |
| Prototype / proof of concept | **Exceeds** | Full working platform live on Akash |
| Training & data strategy | **Covered** | CPT + SFT + DPO pipeline, DATASET_CARD |
| Integration plan | **Covered** | 4 client interfaces documented |
| Roadmap with milestones | **Gap** | Not in repo |
| Open-source components | **Covered** | MIT code, AGPL model adapter |
| Documentation | **Covered** | READMEs, MODEL_CARD, deploy docs |
| Developer-facing APIs/SDKs | **Strong** | OpenAI-compatible API, Python CLI, MCP server, VS Code extension |

### Key RFP Gaps to Close

1. **Adversarial robustness** — Run planned DPO training. RFP explicitly requires this.
2. **Roadmap document** — RFP asks for "roadmap with milestones and success metrics."
3. **Scalability narrative** — Document multi-GPU / auto-scaling strategy.
4. **Security hardening** — Fix critical issues below before submission.

---

## Critical Issues (Must Fix Before Any Public Deploy)

### 1. Leaked Secrets in Git

**File:** `deploy/.env`

```
HUGGING_FACE_HUB_TOKEN=hf_xVLjLW...  (line 4)
WANDB_API_KEY=wandb_v1_Jvc...         (line 5)
SSH_PASSWORD=6Zw4TSX9...              (line 6)
```

**Impact:** Full access to HuggingFace account, W&B training logs, and SSH into training containers.

**Action:**
- Rotate ALL three tokens immediately
- Add `deploy/.env` to `.gitignore`
- Use Akash SDL env injection or sealed secrets

---

### 2. Jupyter Lab Exposed Without Auth

**File:** `deploy/entrypoint.sh:25`

```bash
nohup jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root \
  --NotebookApp.token='' --NotebookApp.password=''
```

Port 8888 globally exposed in `train.sdl.yml`. Anyone with network access can execute arbitrary Python as root.

**Action:** Set token/password, or remove Jupyter from production entrypoint.

---

### 3. Hardcoded Password in Training SDL

**File:** `deploy/train-fresh.sdl.yml:18`

```bash
echo 'root:slm@training' | chpasswd
```

Other scripts correctly use `$SSH_PASSWORD` env var. This one doesn't.

**Action:** Replace with `$SSH_PASSWORD` env var like other scripts.

---

### 4. Prompt Injection via Helius Transaction Data

**File:** `slm-web/app/api/explain/tx/route.ts:36-59`

Untrusted Helius API response fields (`txData.description`, etc.) interpolated directly into LLM prompt. If Helius returns crafted data, it becomes a prompt injection vector.

**Action:** Sanitize/escape external data. Use structured prompting with clear delimiters.

---

## High Priority Issues (Fix Before Public Beta)

### 5. Missing Security Headers

**File:** `slm-web/next.config.mjs`

Empty config — no CSP, HSTS, X-Frame-Options, X-Content-Type-Options, or Referrer-Policy.

**Action:** Add `headers()` in next.config with standard security headers.

---

### 6. next-auth Beta Version

**File:** `slm-web/package.json:33`

```json
"next-auth": "5.0.0-beta.25"
```

Beta may have unpatched vulnerabilities.

**Action:** Pin to latest beta or upgrade when stable v5 ships.

---

### 7. Upstream Error Disclosure

**File:** `slm-web/app/api/chat/route.ts:98`

Raw SGLang error text forwarded to client. Could leak internal URLs, server versions, or stack traces.

**Action:** Return generic error message to client, log full error server-side.

---

### 8. VS Code API Key in Plaintext Settings

**File:** `slm-vscode/src/settings.ts:15`

Reads API key from `vscode.workspace.getConfiguration("slm")` — stored in plaintext in `~/.config/Code/User/settings.json`.

**Action:** Migrate to `vscode.SecretStorage` API.

---

### 9. MCP Server CORS: Wildcard Origin

**File:** `slm-mcp/src/index.ts:181`

```
Access-Control-Allow-Origin: *
```

**Action:** Restrict to known origins or make configurable.

---

### 10. SSH Root Login with Password Auth

**File:** `deploy/entrypoint.sh:12-19`

`PermitRootLogin yes` + password authentication enabled. Globally exposed on port 22.

**Action:** Switch to key-based SSH auth. Disable root login if possible.

---

### 11. Containers Run as Root

RAG API Dockerfile has no `USER` directive. Training containers run everything as root.

**Action:** Add non-root user in Dockerfiles.

---

## Medium Priority Issues (Fix Before GA)

### 12. No API Key Rotation or Revocation

**File:** `slm-web/lib/db.ts`

Keys generated once on user creation, never expire. No revocation mechanism.

**Action:** Add key rotation endpoint + expiry field in Prisma schema.

---

### 13. localStorage API Key Storage (Web Client)

**File:** `slm-web/hooks/use-api-key.ts:14-22`

API key stored in plaintext in localStorage. XSS attack = key theft.

**Action:** Use httpOnly cookie or session-based approach.

---

### 14. No Input Size Limits

- Chat messages array unbounded — `slm-web/app/api/chat/route.ts`
- CLI file reads unconstrained — `slm-cli/slm_cli/main.py:179`
- MCP code review input unbounded — `slm-mcp/src/tools/review-code.ts:6`

**Action:** Add max content length checks on all API routes and client inputs.

---

### 15. RAG API SSRF Risk

**File:** `deploy/rag-api/app.py:534-571`

`/ingest` endpoint accepts arbitrary user-supplied URLs without scheme or host validation.

**Action:** URL allowlist or scheme validation (HTTPS only, no internal IPs).

---

### 16. No Resource Limits on RAG Embedding

**File:** `deploy/rag-api/app.py:364-365`

No pagination or memory limits when embedding large document sets. OOM risk.

**Action:** Add max document size + batch limits.

---

### 17. Internal Services Over HTTP

**File:** `deploy/inference.sdl.yml:63-65`

SGLang and Qdrant communicate over unencrypted HTTP. Documented as known limitation in `deploy/README.md:114-120`.

**Action:** Deploy Caddy sidecar (already proposed in README).

---

### 18. RAG Context Prompt Injection

**File:** `slm-web/app/api/chat/route.ts:45-47`

RAG results injected into system context. Lower risk than Helius (controlled data source), but still a vector.

**Action:** Wrap RAG context in structured delimiters, add sanitization.

---

## Low Priority Issues (Polish)

### 19. API Endpoint Inconsistency

VS Code autocomplete uses `/v1/chat/completions` (OpenAI-compat). CLI/MCP use `/api/chat`. Not a bug (LiteLLM serves both), but should be documented clearly.

---

### 20. Deprecated Pattern Detection Inconsistency

- VS Code checks `ctx.bumps.get()` — MCP doesn't
- CLI/MCP check `closed account discriminator` — VS Code doesn't

**Action:** Unify pattern lists across all clients.

---

### 21. Prisma Schema Improvements

- `schema.prisma:14` — `provider` field is String, should be enum
- `schema.prisma:36` — `onDelete: SetNull` creates orphaned usage records, consider Cascade

---

### 22. Rate Limit Minor Race Condition

**File:** `slm-web/lib/rate-limit.ts:41,57`

Entry added then removed if over limit. Theoretically safe due to Redis pipeline, but slightly wasteful.

---

### 23. W&B Key Present but Disabled

`deploy/.env:5` has W&B key but `deploy/train.sdl.yml:9` sets `WANDB_MODE=disabled`. Remove unused key.

---

## What's Production-Ready

| Area | Status | Notes |
|------|--------|-------|
| Auth (NextAuth + OAuth) | Solid | JWT strategy, proper callbacks, session handling |
| Rate limiting | Solid | Redis sliding window, per-tier limits, proper headers |
| DB schema | Solid | Proper indexes, composite uniques, cascading deletes |
| API route auth checks | Solid | Session ownership verified on all CRUD endpoints |
| CLI secret storage | Solid | OS keyring with TOML fallback |
| API key generation | Solid | `crypto.randomUUID()`, prefixed with `slm_` |
| Multi-client architecture | Solid | CLI + MCP + VS Code + Web all hitting same API |
| Persistent chat history | Solid | Prisma + Neon PostgreSQL, session-scoped, ownership-enforced |
| Documentation | Good | README, MODEL_CARD, deploy docs all present |
| Streaming implementation | Good | SSE properly handled with abort controllers |
| Diagnostics / quick-fixes | Good | Pattern detection with actionable suggestions |
| Eval benchmarks | Good | 85% on 80-task Solana benchmark, 90% HumanEval |

---

## Recommended Fix Order

| When | What |
|------|------|
| **Today** | Rotate leaked secrets (`deploy/.env`). Add to `.gitignore`. |
| **Day 1-2** | Fix Jupyter auth, SSH hardening, hardcoded password |
| **Day 2-3** | Security headers, error sanitization, prompt injection guards |
| **Day 3-4** | VS Code SecretStorage migration, CORS restriction, input limits |
| **Day 5** | Key rotation mechanism, RAG SSRF protection |
| **Week 2** | Caddy sidecar, non-root containers, pattern list unification |
| **Week 2-3** | Run DPO training, write roadmap doc, scalability narrative |

---

## Verification Checklist

After fixes:

- [ ] `git log -- deploy/.env` — confirm secrets never committed to remote
- [ ] `curl -v https://<deploy-url>` — verify security headers (CSP, HSTS, X-Frame-Options)
- [ ] Test prompt injection: send crafted Helius-like payload through `/api/explain/tx`
- [ ] `curl http://<training-ip>:8888` — verify Jupyter requires auth
- [ ] `npm audit` in slm-web, slm-mcp — no critical vulnerabilities
- [ ] `pip audit` in slm-cli — no critical vulnerabilities
- [ ] Blast `/api/chat` — verify 429 rate limit responses
- [ ] VS Code stores key in SecretStorage (not settings.json)
- [ ] Adversarial eval score > 70% after DPO training
- [ ] Roadmap document exists with milestones and success metrics
