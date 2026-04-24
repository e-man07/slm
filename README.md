# Sealevel — Solana Language Model

> The Solana coding AI that actually knows Solana.

[![Eval](https://img.shields.io/badge/Solana_Eval-85%25-brightgreen)](./results/phase1/eval_results.json)
[![HumanEval](https://img.shields.io/badge/HumanEval-90%25-brightgreen)](#benchmarks)
[![Model](https://img.shields.io/badge/Model-Qwen2.5--Coder--7B--Instruct-blue)](https://huggingface.co/WhyParabola/slm-solana-lora)
[![License](https://img.shields.io/badge/License-MIT-lightgrey)](#license)

Sealevel is a fine-tuned coding LLM specialized for Solana and Anchor development. Built on Qwen2.5-Coder-7B-Instruct (7B dense) with QLoRA on 731K Solana records, it scores **85%** on a 80-task Solana/Anchor benchmark and **90%** on HumanEval (general coding).

Use it in your **browser**, **terminal**, **VS Code**, or via **Claude Code / Cursor / Windsurf** through MCP.

---

## Quick Start

### Web
```
https://sealevel.tech
```

### CLI
```bash
pip install sealevel-cli
slm config --api-key sk-slm-xxx
slm chat "How do I derive a PDA in Anchor?"
```

### VS Code
Install **Sealevel - Solana Language Model** from the Marketplace, or:
```bash
code --install-extension slm-vscode-0.1.0.vsix
```

### Claude Code / Cursor / Windsurf (MCP)
```bash
claude mcp add --transport http slm-solana https://slm-mcp.run.app/mcp
```

### API (OpenAI-compatible)
```bash
curl https://api.slm.dev/v1/chat/completions \
  -H "Authorization: Bearer sk-slm-xxx" \
  -H "Content-Type: application/json" \
  -d '{"model":"slm-solana","messages":[{"role":"user","content":"Write a token transfer in Anchor"}]}'
```

---

## What It Does

- **Chat** — Ask Solana/Anchor questions, get accurate, modern-syntax answers
- **Generate** — Scaffold Anchor programs (escrow, staking, AMM, NFT, DAO)
- **Review** — Security scan for deprecated patterns, missing checks
- **Migrate** — Convert old Anchor code to 0.30+ patterns
- **Explain Tx** — Decode Solana transactions by signature
- **Explain Error** — Look up error codes (Token, Anchor, System, ATA)
- **Autocomplete** — Inline suggestions in VS Code

---

## Architecture

```
     ┌─────────────────┐
     │   Developer     │
     └────┬────────────┘
          │
   ┌──────┴───────┬──────────┬──────────┐
   ▼              ▼          ▼          ▼
 Web UI       CLI         VS Code    MCP Server
 (Vercel)   (PyPI)      (Marketplace) (Cloud Run)
   │              │          │          │
   └──────┬───────┴──────────┴──────────┘
          ▼
    LiteLLM Proxy  (OpenAI-compatible, rate-limited)
          │
          ▼
        SGLang  ←── LoRA adapter (HF: WhyParabola/slm-solana-lora)
        (H100 on Akash, Qwen2.5-Coder-7B-Instruct base)
          ▲
          │
      RAG API  ←── Qdrant (latest Solana/Anchor docs)
```

---

## Project Structure

| Directory | Purpose |
|---|---|
| `training/` | CPT, SFT, DPO training scripts (Unsloth + PyTorch) |
| `scripts/` | 38 data pipeline scripts (collection → dedup → filter → prepare) |
| `data/` | 741K CPT records, 731K SFT records ([dataset card](./data/DATASET_CARD.md)) |
| `synthetic/` | 14 template-based Q&A generators |
| `deploy/` | Akash SDL files, Dockerfiles for inference stack |
| `slm-web/` | Next.js 16 web app (chat, explainer, docs, dashboard) |
| `slm-cli/` | Python CLI (`slm chat`, `slm gen`, `slm review`, etc.) |
| `slm-vscode/` | VS Code extension (`@slm` chat, autocomplete) |
| `slm-mcp/` | MCP server (Claude Code, Cursor, Windsurf integration) |
| `results/` | Eval results + LoRA checkpoints |

---

## Benchmarks

### Solana/Anchor (80 tasks)

| Category | Score |
|---|---|
| PDA Derivation | 14/15 (93%) |
| Anchor Constraints | 15/15 (100%) |
| SPL Token Ops | 10/10 (100%) |
| CPI Patterns | 9/10 (90%) |
| Error Handling | 9/10 (90%) |
| Transaction Construction | 7/10 (70%) |
| Adversarial | 4/10 (40%) |
| **Overall** | **68/80 (85%)** |

### HumanEval (general coding)
**18/20 (90%)** — fine-tuning preserved general programming ability.

Full results: [`results/phase1/eval_results.json`](./results/phase1/eval_results.json)

---

## Deployment Status

| Component | Status |
|---|---|
| Data pipeline | Live (741K records) |
| Model training | Phase 2 SFT complete (LoRA on HF) |
| Inference (SGLang + LiteLLM + Qdrant + RAG) | Live on Akash H100 |
| Web app | Ready for Vercel (env vars needed) |
| CLI | Ready for PyPI |
| VS Code extension | Ready for Marketplace |
| MCP server | Ready for Cloud Run (HTTP transport) |

---

## Development

### Run web app locally
```bash
cd slm-web
npm install --legacy-peer-deps
cp .env.example .env.local  # fill in your keys
npm run dev
```

### Run CLI locally
```bash
cd slm-cli
pip install -e .
slm --help
```

### Run MCP server locally
```bash
cd slm-mcp
npm install && npm run build
MCP_TRANSPORT=http PORT=8080 SLM_API_URL=https://... node dist/index.js
```

### Train model (Akash H100)
See [deploy/README.md](./deploy/README.md) for training container setup.

---

## Contributing

- Issues / feature requests: GitHub Issues
- Pull requests welcome — run tests first (`npm test` / `pytest`)
- See component-specific READMEs for dev setup

---

## License

MIT for all code.

**Dataset note:** Training data includes Lumo Labs datasets under AGPL-3.0. See [DATASET_CARD.md](./data/DATASET_CARD.md) for full license breakdown.

---

## Acknowledgments

- **Qwen Team** — base model (Qwen2.5-Coder-7B-Instruct)
- **Unsloth** — 2x faster fine-tuning
- **Solana Foundation** — Sealevel RFP support
- **Akash Network** — decentralized GPU compute
- **Lumo Labs** — Solana-focused datasets
