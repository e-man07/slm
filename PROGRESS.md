# SLM Project - Progress Tracker

Last updated: 2026-04-05 (end of day)

Cross-referenced against [`final-slm-research.md`](final-slm-research.md).

---

## Overall Status

| Category | Completeness | Notes |
|----------|-------------|-------|
| Data Pipeline (Phase 0-1.5) | **100%** | 741K records, curated subsets, DVC pipeline |
| Model Training (Phase 2) | **100%** | 87.5% eval, checkpoint needs re-training |
| Web Application (Phase 3-4) | **100%** | 7 pages, 6 API routes, 40+ components |
| Auth + Rate Limiting | **100%** | GitHub OAuth, Redis rate limiting, Neon Postgres |
| Python CLI | **90%** | Built, tested, not published to PyPI |
| VS Code Extension | **70%** | Core chat works, no CodeAction/diagnostics |
| Inference Deployment | **0%** | Nothing deployed — blocks all live features |
| RAG Pipeline | **0%** | Not started |
| Grants/Community | **0%** | Hackathon starts April 6 |

**Tests: 145 total (101 web + 28 CLI + 16 VS Code) — all passing**

---

## Phase 0: Infrastructure

| Item | Status | Notes |
|------|--------|-------|
| Akash Network credits | DONE | ~$200 remaining |
| HuggingFace Hub account | DONE | Token configured |
| GitHub OAuth App | DONE | Client ID + Secret in .env.local |
| Neon Postgres | DONE | DATABASE_URL configured, tables created |
| Redis | DONE (local) | Docker container on localhost:6379 |
| Helius API | DONE | API key in .env.local |
| Container persistence (tini) | DONE | Solved recycling issue |
| Domain | NOT DONE | No domain registered |
| Vercel deployment | NOT DONE | |
| Hosted Redis (production) | NOT DONE | Need Upstash for prod |

---

## Phase 1: Data Collection

| Source | Status | Records | License |
|--------|--------|---------|---------|
| GitHub repos (7) | DONE | ~12K | Apache-2.0 |
| Lumo HF datasets (4) | DONE | ~565K | AGPL-3.0 |
| Strandset-Rust-v1 | DONE | 163K | Apache-2.0 |
| Doc crawls (4 sites) | DONE | ~760 | RAG-only |
| Stack Exchange | DONE | RAG-only | CC-BY-SA (excluded) |
| On-chain IDLs | DONE | ~55 | Apache-2.0 |
| Synthetic data (14 scripts) | DONE | ~353 | Permissible |
| Migration examples | DONE | 30 pairs | Apache-2.0 |
| Vulnerability datasets | DONE | 376 DPO pairs | For DPO |
| learn-rust, stack-rust-clean | DONE | ~19K | Apache-2.0/OpenRAIL |

**Total: 741,922 CPT records, 731,979 SFT records, 397 DPO pairs**

---

## Phase 1.5: Data Pipeline

| Stage | Status |
|-------|--------|
| Schema standardization | DONE |
| Dedup (exact + MinHash LSH) | DONE |
| Quality filtering | DONE |
| Anchor version tagging | DONE |
| CPT/SFT format preparation | DONE |
| Dataset curation (10K, 50K subsets) | DONE |
| License filtering | DONE |
| DVC pipeline (20+ stages) | DONE |
| HuggingFace publishing script | DONE |

### Training Data (Local)

| File | Records | Size |
|------|---------|------|
| sft_10k.jsonl | 10,000 | 28 MB |
| sft_50k.jsonl | 50,000 | 123 MB |
| sft_train.jsonl | 731,979 | 1.1 GB |
| cpt_train.jsonl | 741,922 | 989 MB |
| dpo_chosen.jsonl | 397 | 837 KB |
| dpo_rejected.jsonl | 397 | 718 KB |

---

## Phase 2: Model Training

### Results

| Run | Data | Eval Score | Status |
|-----|------|-----------|--------|
| **Phase 1 SFT** | 10K, 1 epoch | **87.5% (70/80)** | Best — checkpoint lost (needs re-training) |
| Phase 2 SFT | 50K, 3 epochs | 83.75% (67/80) | Checkpoint saved locally |
| DPO | 397 pairs, 2 epochs | 81.25% (65/80) | Degraded quality — overfitted |

### Eval Breakdown (Phase 1 — Best Model)

| Category | Tasks | Passed | Rate |
|----------|-------|--------|------|
| PDA Derivation | 15 | 14 | 93% |
| Anchor Constraints | 15 | 13 | 87% |
| SPL Token Ops | 10 | 10 | 100% |
| CPI Patterns | 10 | 10 | 100% |
| Error Handling | 10 | 10 | 100% |
| Tx Construction | 10 | 10 | 100% |
| Adversarial | 10 | 3 | 30% |

### Checkpoints (Local)

- `results/checkpoints/sft-checkpoint-2000/` — Phase 2 LoRA adapter (51MB)
- Phase 1 checkpoint — **LOST** (overwritten, needs 1.5hr re-training on H100)

---

## Phase 3-4: Web Application

### Tech Stack
- Next.js 16, React 19, Tailwind v4
- shadcn/ui (radix-maia, olive, zero radius)
- JetBrains Mono + Geist fonts
- Hugeicons, next-themes
- NextAuth.js (GitHub OAuth)
- Neon Postgres, Redis (ioredis)
- Vitest + Testing Library

### Pages (7/7 — ALL BUILT)

| Page | Route | Features |
|------|-------|----------|
| Landing | `/` | Hero, features grid, install tabs (CLI/API/Ollama/VS Code), eval embed |
| Chat | `/chat` | Streaming, markdown rendering, code blocks, feedback buttons, typing indicator, suggested prompts, try-it-out from docs |
| Tx Explainer | `/explain/tx` | Signature input, Helius parsing, structured data, collapsible instructions, AI explanation |
| Error Decoder | `/explain/error` | Code input, 324-error lookup, popular errors, AI explanation |
| API Docs | `/docs` | Sidebar nav, 8 sections, tabbed code examples, try-it-out buttons |
| Eval Dashboard | `/eval` | 87.5% hero, category bar chart, individual task accordion |
| Dashboard | `/dashboard` | GitHub OAuth login, API key display, usage stats, 7-day chart |

### API Routes (6 — ALL BUILT)

| Route | Method | Auth | Rate Limited | Features |
|-------|--------|------|-------------|----------|
| `/api/chat` | POST | Optional | Yes | SSE streaming, system prompt injection, OpenAI-compatible |
| `/api/explain/tx` | POST | Optional | Yes | Helius fetch + structured data + AI streaming |
| `/api/explain/error` | POST | Optional | Yes | Static lookup + AI streaming |
| `/api/health` | GET | No | No | SGLang connectivity, ok/down status |
| `/api/auth/[...nextauth]` | GET/POST | N/A | No | GitHub OAuth flow |
| `/api/usage` | GET | Required | No | Per-key usage stats |

### Components (40+)

**Custom components (21):**
- Layout: NavBar (with logo SVG), Footer, PageLayout
- Chat: ChatMessage (markdown + feedback + typing indicator), ChatInput, StreamingText
- Explain: TxSignatureInput, TxResult (with instruction accordion), ErrorCodeInput, ErrorResult
- Eval: EvalScoreHero, EvalCategoryChart, EvalTaskTable
- Dashboard: ApiKeyDisplay, UsageChart, UsageStats
- Shared: CodeBlock (shiki server-side), CopyButton

**shadcn/ui primitives (19):**
input, input-group, textarea, card, badge, tabs, table, accordion, sonner, tooltip, skeleton, separator, scroll-area, switch, dialog, dropdown-menu, avatar, command, button

### Utilities (15)

| File | Purpose |
|------|---------|
| `constants.ts` | System prompt (6 guardrails), API URLs, rate limits |
| `sse.ts` | SSE stream parser (async generator) |
| `api-client.ts` | Typed fetch helpers (chat, tx, error) |
| `errors.ts` | Error lookup from static table |
| `helius.ts` | Helius API client + helpers |
| `shiki.ts` | Syntax highlighter singleton |
| `auth.ts` | NextAuth config, GitHub provider, API key generation |
| `db.ts` | Neon Postgres client, user/usage management |
| `middleware.ts` | Rate limit wrapper, API key extraction, tier resolution |
| `rate-limit.ts` | Redis sliding window rate limiter |
| `redis.ts` | Redis client singleton |
| `utils.ts` | cn() class merger |

### Hooks (3)

| Hook | Purpose |
|------|---------|
| `use-chat.ts` | Chat state, SSE streaming, message management |
| `use-streaming.ts` | Low-level SSE consumption |
| `use-api-key.ts` | localStorage API key management |

### Data Files

| File | Content |
|------|---------|
| `eval-results.json` | 80-task eval results (87.5% overall) |
| `error-table.json` | 15 programs, 324 errors |

### Static Assets

| File | Type |
|------|------|
| `public/logo.svg` | SLM wordmark |
| `public/og-image.svg` | Social preview (needs PNG conversion) |
| `app/favicon.ico` | Favicon |

### Tests (101)

| Category | Files | Tests |
|----------|-------|-------|
| Quick fixes (#1-10) | 10 | 21 |
| Medium fixes (#11-17) | 7 | 38 |
| Feature #18 (error table) | 1 | 12 |
| Feature #19 (GitHub OAuth) | 1 | 11 |
| Feature #20 (rate limiting) | 1 | 12 |
| Feature #21 (usage stats) | 1 | 7 |
| **Total** | **21** | **101** |

---

## External Packages

### Python CLI (`slm-cli/`)

| Item | Status |
|------|--------|
| typer + httpx + rich | DONE |
| `slm chat` command | DONE |
| `slm explain --tx` | DONE |
| `slm explain --error` | DONE |
| `slm config` | DONE |
| SSE streaming | DONE |
| Rich formatting | DONE |
| Tests (28 passing) | DONE |
| PyPI publishing | NOT DONE |

### VS Code Extension (`slm-vscode/`)

| Item | Status |
|------|--------|
| Chat Participant (`@slm`) | DONE |
| SSE streaming to chat | DONE |
| `slm.explainError` command | DONE |
| `slm.explainTx` command | DONE |
| Settings (apiKey, apiUrl, mode) | DONE |
| Tests (16 passing) | DONE |
| CodeAction Provider (rust-analyzer) | NOT DONE |
| Diagnostic interception | NOT DONE |
| Ollama local fallback | NOT DONE |
| Marketplace publishing | NOT DONE |

---

## What's NOT Built — Prioritized

### Critical Path to Launch (~4-5 hours)

| # | Item | Effort | Blocks |
|---|------|--------|--------|
| 1 | Re-run Phase 1 SFT (recover 87.5% model) | 1.5 hrs | Everything |
| 2 | Merge LoRA + export model to HuggingFace | 30 min | Inference |
| 3 | Deploy SGLang on Akash | 1-2 hrs | All API routes |
| 4 | Deploy web app to Vercel | 30 min | Public demo |
| 5 | Domain setup | 30 min | Hackathon URL |
| 6 | Hosted Redis (Upstash free tier) | 15 min | Prod rate limiting |
| 7 | Run DB migration on Neon | 5 min | Auth/dashboard |

### High Priority (~5 hours)

| # | Item | Effort |
|---|------|--------|
| 8 | Error table expansion (324→1,914 errors) | 2-3 hrs |
| 9 | OG image: SVG→PNG conversion | 15 min |
| 10 | GGUF export for Ollama | 1 hr |
| 11 | Package VS Code extension (.vsix) | 30 min |
| 12 | Publish CLI to PyPI | 1 hr |

### Medium Priority (~10 hours)

| # | Item | Effort |
|---|------|--------|
| 13 | VS Code CodeAction + diagnostics | 4-6 hrs |
| 14 | CI/CD (GitHub Actions) | 2-3 hrs |
| 15 | Ollama fallback in VS Code | 2 hrs |
| 16 | UptimeRobot monitoring | 15 min |
| 17 | Caddy TLS for Akash inference | 2-3 hrs |

### Post-Hackathon (~3-4 weeks)

| # | Item | Effort |
|---|------|--------|
| 18 | RAG pipeline (Qdrant + embeddings + reranking) | 2-3 weeks |
| 19 | Fix DPO (hand-curated pairs, train on SFT checkpoint) | 3-5 days |
| 20 | Grant applications (Colosseum, Superteam, SLM RFP) | 3-5 days each |
| 21 | LiteLLM proxy for multi-tenant | 1-2 days |
| 22 | Backup strategy | 1 day |
| 23 | Post-launch retraining plan | 1 day |

---

## Key Technical Learnings

### Model Training
- Data quality > data quantity: 10K curated records beat 50K (87.5% vs 83.75%)
- DPO with small datasets overfits: 397 pairs degraded quality
- `torch._dynamo.config.disable = True` required for MoE models
- Eval can't run alongside training on 80GB GPU
- `attn_implementation="eager"` needed for inference
- `batch_size=1, grad_accum=8` fits 80GB; batch_size=2 OOMs
- H100 ~2x faster than A100 (31s vs 57s per step)

### Infrastructure
- Akash containers recycle without tini as PID 1
- `set -e` in entrypoint kills container on `pgrep` returning 1
- TRL 0.24.0 has broken optional imports (llm_blender, weave, mergekit)
- `pip install --force-reinstall` can break torch/torchvision compatibility
- Em dash characters (—) cause bash syntax errors in heredocs

### Web App
- shadcn/ui v4 uses `sonner` not `toast`
- Shiki works as async server component (zero client JS)
- `react-markdown` + `remark-gfm` for chat message rendering
- NextAuth v5 beta for App Router
- Redis sorted sets for sliding window rate limiting

---

## Environment Configuration

```
# .env.local (gitignored)
GITHUB_CLIENT_ID=Ov23liRB9vfy1lDez0C3
GITHUB_CLIENT_SECRET=<configured>
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=<configured>
REDIS_URL=redis://localhost:6379
DATABASE_URL=postgresql://...@neon.tech/neondb
HELIUS_API_KEY=<configured>
SGLANG_URL=http://localhost:30000
```

---

## Repository Structure

```
slm/
├── data/final/           # Training data (local)
├── results/              # Eval results + checkpoints
├── training/             # Training scripts (train_sft, train_dpo, eval)
├── scripts/              # Data pipeline scripts
├── configs/              # sources.toml, licenses.csv
├── deploy/               # Akash SDL files
├── slm-web/              # Next.js web application
│   ├── app/              # 7 pages + 6 API routes
│   ├── components/       # 21 custom + 19 shadcn
│   ├── lib/              # 15 utilities
│   ├── hooks/            # 3 hooks
│   ├── data/             # eval-results.json, error-table.json
│   ├── public/           # logo.svg, og-image.svg
│   ├── docs/             # 9 product spec documents
│   └── __tests__/        # 21 test files, 101 tests
├── slm-cli/              # Python CLI (typer + httpx + rich)
│   ├── slm_cli/          # 5 source files
│   └── tests/            # 4 test files, 28 tests
└── slm-vscode/           # VS Code extension
    ├── src/              # 3 source files
    └── test/             # 2 test files, 16 tests
```
