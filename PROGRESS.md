# SLM Project — Progress Tracker

Cross-referenced against [`final-slm-research.md`](final-slm-research.md). Sections marked with the status of each item from the research blueprint.

---

## Phase 0: Infrastructure and Accounts

| Item | Status | Notes |
|------|--------|-------|
| Akash Network account + credits | DONE | $1,300 in credits available |
| HuggingFace Hub account + token | DONE | Token: configured in `deploy/.env` and SDL files |
| Weights & Biases account + API key | DONE | Key configured in `deploy/.env` and SDL files |
| Akash training deployment (A100 80GB) | DONE | `deploy/train.sdl.yml` — deployed and running |
| Akash inference deployment | NOT STARTED | `deploy/inference.sdl.yml` — written but not deployed yet (post-training) |
| VPS for Qdrant/API/scrapers | NOT STARTED | Planned as part of inference SDL (multi-service) |

### Training Container Details
- **Provider**: `provider.a100.dsm.val.akash.pub`
- **GPU**: NVIDIA A100-SXM4-80GB
- **Image**: `pytorch/pytorch:2.5.1-cuda12.4-cudnn9-devel`
- **Resources**: 16 CPU, 64GB RAM (provider gives 2TB), 200GB persistent storage
- **Access**: SSH on port 31301, Jupyter on port 32045
- **Cost**: ~$1.27/hour
- **Persistent storage**: `/workspace` (data, scripts, model cache, checkpoints survive restarts)

---

## Phase 1: Data Collection

| Source | Status | Script | Output |
|--------|--------|--------|--------|
| GitHub repos (Anchor, SPL, Agave, etc.) | DONE | `scripts/collect.py` | `data/processed/anchor.jsonl`, `spl.jsonl`, `agave.jsonl`, `program-examples.jsonl`, `developer-content.jsonl`, `solana-cookbook.jsonl` |
| HuggingFace datasets (Lumo, learn-rust, stack-rust) | DONE | `scripts/collect_hf.py` | `data/processed/hf-lumo-fart.jsonl`, `hf-lumo-novel.jsonl`, `hf-learn-rust.jsonl`, `hf-stack-rust-clean.jsonl` |
| Doc site crawling (docs.rs, Helius, Metaplex) | DONE | `scripts/crawl_docs.py` | `data/processed/crawl-anchor-rustdoc.jsonl`, `crawl-helius-*.jsonl`, `crawl-metaplex-docs.jsonl` |
| Forum crawling (forum.solana.com) | DONE | `scripts/crawl_forum.py` | `data/processed/forum-solana.jsonl` |
| Stack Exchange (RAG-only) | DONE | `scripts/collect_stackexchange.py` | Excluded from training per license |
| On-chain data (IDLs, txs via Helius) | DONE | `scripts/collect_onchain.py` | `data/processed/` |
| Anchor migration examples (old->new) | DONE | `scripts/migrate_examples.py` | 50-100 migration pairs |
| Synthetic data (OSS-Instruct, Evol-Instruct, GLAN) | DONE | `scripts/gen_synthetic.py` + 12 bulk scripts + 2 extra rounds | `data/processed/synthetic-bulk{1-12}.jsonl`, `synthetic-evol-*.jsonl`, `synthetic-oss-*.jsonl`, `synthetic-glan-*.jsonl` |
| License audit | DONE | `scripts/fix_licenses.py`, `configs/licenses.csv` | Apache-2.0 repos free, SE excluded, Helius/Metaplex RAG-only |

### Batch request artifacts
- `synthetic/oss-instruct-batch.jsonl`
- `synthetic/evol-instruct-batch.jsonl`
- `synthetic/glan-batch.jsonl`

---

## Phase 1.5: Data Pipeline Architecture

| Stage | Status | Script | Notes |
|-------|--------|--------|-------|
| Schema standardization | DONE | `scripts/schema.py` | Shared data model with `id`, `source`, `source_type`, `content`, `language`, `license`, `metadata` |
| Source registry | DONE | `configs/sources.toml` | 15+ sources with license info |
| Exact dedup (SHA-256) | DONE | `scripts/dedup.py` | Two-pass: exact + near-dedup |
| Near-dedup (MinHash LSH) | DONE | `scripts/dedup.py` | 128 perms, 3-shingles, 0.8 threshold via datasketch |
| Quality filtering | DONE | `scripts/filter.py`, `scripts/filter_perplexity.py` | rustfmt check, length filter, KenLM perplexity |
| Anchor version tagging | DONE | `scripts/tag_anchor_version.py` | Modern (0.30+) vs legacy classifier |
| CPT/SFT format preparation | DONE | `scripts/prepare.py` | CPT `{"text": "..."}` and SFT ChatML format |
| DPO data preparation | DONE | `training/prepare_dpo.py` | Merges chosen/rejected JSONL files |
| Dataset versioning & publishing | DONE | `scripts/publish.py` | HuggingFace Hub upload support |
| Dataset card | DONE | `data/DATASET_CARD.md` | Full provenance documentation |
| DVC pipeline | DONE | `dvc.yaml` | 20+ reproducible stages |

### Final Training Data
- **CPT corpus**: `data/final/cpt_train.jsonl` — **1.4 GB, 578,186 records**
- **SFT instructions**: `data/final/sft_train.jsonl` — **107 MB**
- **DPO pairs**: `data/processed/dpo-chosen*.jsonl`, `dpo-rejected*.jsonl`
- **Stats**: `data/final/dataset_meta.json`

---

## Phase 2: Model Selection, Training, and Evaluation

### Base Model
| Item | Status | Notes |
|------|--------|-------|
| Model selected | DONE | Qwen3-Coder-30B-A3B-Instruct (MoE, 30B total / 3.3B active) |
| Model downloaded to Akash | DONE | Cached at `/workspace/cache/huggingface/models--Qwen--Qwen3-Coder-30B-A3B-Instruct/snapshots/b2cff646eb4bb1d68355c01b18ae02e7cf42d120` |

### Training Pipeline
| Stage | Status | Script | Notes |
|-------|--------|--------|-------|
| CPT (Continued Pre-Training) | IN PROGRESS | `training/train_cpt.py` | Running on Akash A100 — step ~14/71,551 as of Mar 28 |
| SFT (Supervised Fine-Tuning) | NOT STARTED | `training/train_sft.py` | Runs after CPT |
| DPO (Direct Preference Optimization) | NOT STARTED | `training/train_dpo.py` | Runs after SFT |

### CPT Training Configuration (Active)
```
Model:       Qwen3-Coder-30B-A3B-Instruct (4-bit quantized)
Framework:   Unsloth + UnslothTrainer
LoRA rank:   32 (alpha: 64)
Seq length:  8,192
Batch:       1 x 8 gradient accumulation
LR:          2e-5 (cosine scheduler)
Epochs:      1
Data:        578,186 samples (572,404 train / 5,782 val)
Total steps: 71,551
GPU memory:  64.7 GB / 80 GB used
Checkpoints: Every 500 steps to /workspace/checkpoints/cpt
Watchdog:    Auto-restart script at /workspace/watchdog.sh
```

### Key Training Issues Resolved
1. **SDL format** — Went through ~6 iterations to get working Akash SDL (env quoting, command/args split, image selection)
2. **Unsloth image** — `unsloth/unsloth:latest` blocked by "no new privileges"; switched to `pytorch/pytorch:2.5.1-cuda12.4-cudnn9-devel`
3. **GPU OOM** — Reduced seq_length from 32768->8192, LoRA r from 64->32
4. **TRL 0.24.0 API changes** — `max_seq_length` renamed to `max_length`, `tokenizer` renamed to `processing_class`
5. **EOS token issue** — Unsloth monkey-patches SFTConfig setting `eos_token='<EOS_TOKEN>'` which doesn't exist in Qwen3 vocab; bypassed by switching to `UnslothTrainer` + `UnslothTrainingArguments` with pre-tokenized data
6. **Container restarts** — Pip packages are ephemeral; created `/workspace/start_training.sh` and `/workspace/watchdog.sh` on persistent storage for auto-recovery

### Evaluation
| Item | Status | Script | Notes |
|------|--------|--------|-------|
| Evaluation harness | DONE | `training/eval.py` (955 lines) | 80 hardcoded Solana eval tasks across 7 categories |
| Baseline eval (unmodified model) | NOT STARTED | `make eval-baseline` | Run before/after training for comparison |
| Checkpoint eval | NOT STARTED | Configured for every 500 steps | |
| Acceptance criteria defined | DONE | In research doc | Solana Bench >=15% improvement, HumanEval <=2pt regression, adversarial >=90% refusal, cargo check >=70% |

### Eval Categories (80 tasks)
- 15 PDA derivation
- 15 Anchor constraints
- 10 SPL token operations
- 10 CPI (cross-program invocation)
- 10 Error handling
- 10 Adversarial (Asymmetric Research debunked patterns)
- 10 Transaction construction

### Alignment/Safety
| Item | Status | Notes |
|------|--------|-------|
| System prompt guardrails | NOT STARTED | 6 rules from Asymmetric Research report |
| DPO preference pairs (200-400) | PARTIAL | DPO data files exist in `data/processed/dpo-*` |
| Runtime output filtering | NOT STARTED | FastAPI middleware for known-bad patterns |

---

## Phase 3: Inference Serving and RAG Pipeline

| Item | Status | Notes |
|------|--------|-------|
| SGLang deployment | NOT STARTED | Configured in `deploy/inference.sdl.yml` |
| LiteLLM proxy | NOT STARTED | Configured in inference SDL |
| Qdrant vector DB | NOT STARTED | Configured in inference SDL |
| RAG API (FastAPI) | NOT STARTED | Placeholder in inference SDL |
| Embedding model (bge-small) | NOT STARTED | |
| Reranking model | NOT STARTED | |
| Context window management | NOT STARTED | 32K budget allocation defined in research |

### Inference SDL Architecture (Written, Not Deployed)
- **sglang**: A100 GPU, 48GB RAM, port 30000
- **litellm**: 2 CPU, 2GB RAM, port 4000 -> exposed as port 80
- **qdrant**: 2 CPU, 4GB RAM, port 6333, 10GB persistent storage
- **rag-api**: 4 CPU, 8GB RAM, port 8080

---

## Phase 4: VS Code Extension, CLI, and API

| Item | Status | Notes |
|------|--------|-------|
| FastAPI backend | NOT STARTED | |
| API auth (LiteLLM + Caddy) | NOT STARTED | |
| VS Code extension | NOT STARTED | |
| Python CLI (`slm chat`, `slm explain`) | NOT STARTED | |
| Rust CLI (stretch goal) | NOT STARTED | |
| Solana error explanation | NOT STARTED | |
| Local Ollama fallback | NOT STARTED | |

---

## Phase 5: Grants and Community

| Item | Status | Notes |
|------|--------|-------|
| SLM RFP response | NOT STARTED | forum.solana.com — still zero replies |
| Colosseum Spring 2026 Hackathon | NOT STARTED | April 6 - May 11, 2026 |
| Superteam India Instagrant | NOT STARTED | Up to $15K, 48-72 hour decision |
| Solana Foundation grant | NOT STARTED | |
| LamportDAO microgrant | NOT STARTED | |

---

## Build System and Orchestration

| Item | Status | Notes |
|------|--------|-------|
| Makefile | DONE | 50+ targets covering data, training, eval, export, utilities |
| DVC pipeline | DONE | `dvc.yaml` with 20+ reproducible stages |
| pyproject.toml | DONE | Project metadata, dependencies |
| Source config | DONE | `configs/sources.toml` |
| License tracking | DONE | `configs/licenses.csv` |

### Key Makefile Targets
```
Data:     make collect, collect-hf, crawl-docs, crawl-forum, dedup, filter, prepare
Synth:    make synthetic-oss, synthetic-evol, synthetic-glan
Training: make cpt, sft, dpo, train (all three)
Eval:     make eval, eval-baseline, eval-compare
Export:   make export-gguf, export-merged, push-hf
Deploy:   make upload-data, gpu-check, disk-check, clean-checkpoints
```

---

## Cross-Cutting Items

| Item | Status | Notes |
|------|--------|-------|
| Testing strategy (unit/integration/regression) | NOT STARTED | Defined in research doc |
| CI/CD pipeline | NOT STARTED | |
| Monitoring & observability | NOT STARTED | |
| User feedback loop | NOT STARTED | |
| Cost tracking | PARTIAL | Akash dashboard tracks credits |
| Backup & disaster recovery | NOT STARTED | |
| Post-launch retraining plan | NOT STARTED | Defined in research doc |

---

## Files on Akash Container (`/workspace/`)

Persistent storage that survives container restarts:

```
/workspace/data/cpt_train.jsonl              # 578K training samples
/workspace/scripts/train_cpt.py              # Current training script
/workspace/checkpoints/cpt/                  # Checkpoint output dir
/workspace/cache/huggingface/models--Qwen--* # Cached model weights
/workspace/start_training.sh                 # Auto-resume launcher
/workspace/watchdog.sh                       # Watchdog daemon (checks every 5 min)
/workspace/cpt_training.log                  # Training output log
/workspace/watchdog.log                      # Watchdog status log
```

---

## Summary

| Category | Status |
|----------|--------|
| **Infrastructure** | DONE (training container running on Akash A100) |
| **Data Collection** | DONE (15+ sources, 578K CPT records, 107MB SFT data) |
| **Data Pipeline** | DONE (schema, dedup, filter, prepare, DVC, publish) |
| **CPT Training** | IN PROGRESS (~10s/step, 71K steps, running with watchdog) |
| **SFT Training** | BLOCKED (waiting on CPT) |
| **DPO Alignment** | BLOCKED (waiting on SFT) |
| **Evaluation** | READY (eval.py written, 80 tasks, not yet run) |
| **Inference Deploy** | NOT STARTED (SDL written) |
| **RAG Pipeline** | NOT STARTED |
| **VS Code Extension** | NOT STARTED |
| **CLI Tool** | NOT STARTED |
| **Grants/Funding** | NOT STARTED |

**Current blocker**: CPT training in progress on Akash A100. Estimated ~8 days for full epoch at current speed (~10s/step). All downstream tasks (SFT, DPO, eval, inference) are blocked on CPT completion.
