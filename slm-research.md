# The complete blueprint for building a Solana coding LLM on $10K

A team of 2–4 developers in India can fine-tune an open-source MoE coding model on Solana/Anchor data, build a RAG pipeline, deploy inference, and ship a VS Code extension plus CLI tool within 14 weeks for roughly $10,000. The optimal stack centers on **Qwen3-Coder-30B-A3B** fine-tuned via **Unsloth QLoRA** on an Akash Network A100, served by **SGLang** on an Akash RTX 4090, with **Qdrant** vector search on an Akash CPU instance. This report covers every tool, service, and resource needed — with verified URLs, current pricing, and practical quickstart guidance — organized across six project phases.

The Solana Foundation's February 2026 SLM RFP (with zero public responses so far) and the Colosseum Spring 2026 Hackathon (April 6–May 11) create an immediate funding window. Lumo Labs' existing datasets (up to 500K Q&A pairs) and the Asymmetric Research misinformation report provide critical training signal. The ecosystem is rapidly converging on an **MCP + Skills** pattern for AI-Solana integration, making this the right moment to build.

---

## Phase 0: Infrastructure and accounts — GPU, platforms, and servers

### Cloud GPU for training

Fine-tuning a 30B MoE model with QLoRA requires a single A100 80GB. **Akash Network** (akash.network) is a decentralized GPU marketplace that undercuts centralized providers by **50–85%**. A100 80GB instances are available at significantly lower rates than centralized alternatives, and the team has **$1,300 in Akash compute credits** — sufficient for the full training pipeline.

Deploy training workloads via the **Akash Console** web UI (console.akash.network) or the Akash CLI (`akash tx deployment create`). Define GPU requirements in an SDL (Stack Definition Language) file specifying the A100 80GB, Docker image (Unsloth), and storage mounts. Akash supports NVIDIA GPU passthrough with full CUDA compatibility.

**Advantages**: Lowest cost for GPU compute, pay in AKT or USDC, no vendor lock-in, built-in deployment dashboard for credit tracking.

**Trade-offs**: Provider reliability varies (no SLA guarantees), cold migrations take longer than managed providers, and debugging networking issues requires familiarity with the SDL deployment spec. SGLang and Unsloth Docker images work without modification on Akash GPU instances.

### Cloud GPU for 24/7 inference serving

A quantized Qwen3-Coder-30B-A3B (AWQ 4-bit) needs roughly **17–20GB VRAM**, fitting comfortably on an RTX 4090 (24GB). **Akash Network RTX 4090 instances** have been observed at **~$100–150/month** depending on supply, making it the cheapest option for 24/7 inference. Deploy via the same Akash Console/CLI used for training, with an SDL specifying the RTX 4090 and persistent storage for model weights.

SGLang can auto-recover from restarts, making it well-suited for Akash's decentralized provider model. Configure the SDL with a health check endpoint so Akash can automatically restart the container if SGLang becomes unresponsive.

**Budget allocation recommendation**: The team's **$1,300 Akash credits** cover both training and inference. Estimated split: ~$500 for training (A100 GPU-hours), ~$600 for inference serving (RTX 4090, ~4–6 months), ~$200 buffer for VPS hosting and experiments. Additional credits can be purchased as needed, and grant funding (Phase 5) can extend the runway.

### HuggingFace Hub

The free tier provides **unlimited public models and datasets** with approximately 100GB of private storage. The Hub Python library (`pip install huggingface_hub`) handles all uploads — from datasets to merged model weights to GGUF quantizations. Model cards and dataset cards are YAML-front-matter Markdown files in the repository root; HuggingFace provides templates through the web editor. The Pro tier ($9/month) unlocks 1TB private storage if needed.

Key documentation: **huggingface.co/docs/hub** (Hub guide), **huggingface.co/docs/datasets/create_dataset** (dataset creation), **huggingface.co/docs/datasets/upload_dataset** (dataset publishing).

### Weights & Biases experiment tracking

The free tier allows **unlimited experiments and runs** for personal projects (no corporate use), with community support and basic storage. This is sufficient for the SLM project. The academic tier (free with .edu email) unlocks all Pro features including 200GB storage and up to 100 seats.

Unsloth integrates natively through HuggingFace's `SFTTrainer` — simply set `report_to="wandb"` in `TrainingArguments` and call `wandb.init(project="slm-finetune")` before training. All loss curves, learning rates, and gradient norms log automatically. A practical tutorial exists at **wandb.ai/byyoung3/Generative-AI/reports/How-to-fine-tune-and-evaluate-Qwen3-with-Unsloth**. Installation: `pip install wandb`, then `wandb login` with your API key from wandb.ai/authorize.

### VPS hosting for Qdrant, API gateway, and scrapers

**Akash Network CPU instances** provide cost-effective VPS hosting for non-GPU workloads. Deploy a CPU-only SDL with 4+ vCPU, 8–16GB RAM, and persistent storage for Qdrant, the FastAPI/LiteLLM gateway, Caddy reverse proxy, and scraper processes. Akash CPU instances cost significantly less than traditional cloud VPS providers.

Deploy all services as a single Akash deployment with multiple containers (Qdrant, FastAPI, Caddy) using Akash's multi-service SDL support, or as separate deployments for independent scaling. Persistent storage ensures Qdrant data and SQLite databases survive container restarts.

---

## Phase 1: Collecting Solana-specific training data at scale

### Web scraping pipeline

The recommended stack is **Playwright → trafilatura** for JavaScript-heavy doc sites and **Scrapy** for large-scale crawling. Playwright (`pip install playwright && playwright install`) renders JS-heavy pages like solana.com/docs, then trafilatura (`pip install trafilatura[all]`) extracts clean text content — benchmarks show trafilatura outperforms readability-lxml, newspaper3k, and goose3 on F1 scores for text extraction. For scrapy integration with JS sites, use **scrapy-playwright** (`pip install scrapy-playwright`).

However, the most efficient approach for documentation is to **clone source repositories directly**. Solana docs source lives at **github.com/solana-foundation/developer-content** (Markdown files), Anchor docs at **github.com/solana-foundation/anchor/tree/master/docs**, and the Cookbook at **github.com/solana-developers/solana-cookbook**. This bypasses scraping entirely for the highest-value documentation.

### GitHub repositories to clone

The Anchor framework has **migrated** from coral-xyz to **github.com/solana-foundation/anchor** (4.8K+ stars). Key repos:

- **solana-foundation/anchor** — The Anchor framework plus documentation
- **solana-labs/solana-program-library** — SPL token programs, governance, stake pool
- **solana-developers/program-examples** — Official examples in Anchor, native Rust, and TypeScript
- **anza-xyz/agave** — The Solana validator client (formerly solana-labs/solana)
- **solana-developers/anchor-examples** — 26 dedicated Anchor examples
- **solana-foundation/developer-content** — Source for solana.com/docs

The GitHub REST API provides 5,000 requests/hour with authentication (create PATs at github.com/settings/tokens). Use `git clone --depth 1` for bulk extraction, then filter for `.rs`, `.md`, and `.toml` files. The topics page at **github.com/topics/anchor-lang** lists 522+ additional repos.

### Solana documentation sites (verified live URLs)

| Site | URL | Best collection method |
|---|---|---|
| Solana Official Docs | **solana.com/docs** | Clone developer-content repo |
| Anchor Docs | **anchor-lang.com/docs** | Clone anchor repo /docs |
| Anchor Rust API | **docs.rs/anchor-lang/latest** | Crawl with Playwright |
| SPL Token Docs | **spl.solana.com/token** | Crawl from SPL repo |
| Solana Cookbook | **solana.com/developers/cookbook** | Clone solana-cookbook repo |
| Solana Developer Forum | **forum.solana.com** | Discourse API |
| Helius Blog | **helius.dev/blog** | Crawl (excellent deep technical articles) |
| Helius Docs | **helius.dev/docs** | Crawl |
| Metaplex Docs | **developers.metaplex.com** | Crawl (rich MDX/React) |
| Token Extensions | **solana.com/docs/tokens** | Part of developer-content |
| Solana Playground | **beta.solpg.io** | Extract example programs |

### Stack Exchange data with licensing caveats

The Solana Stack Exchange data dump (~4.4MB compressed, ~10K+ Q&A posts) is available at **archive.org/details/stackexchange_20251231**, file `solana.stackexchange.com.7z`. Contains Posts.xml, Users.xml, Comments.xml in standard SE format.

**Critical warning**: Since July 2024, Stack Exchange's data dump license **explicitly excludes LLM training**. Starting with the June 2025 dump, SE has added **watermarking/data poisoning** to some archives. The Stack Exchange API (api.stackexchange.com/2.3/) provides 10,000 requests/day with a registered API key (300/day without), at 100 items per page. Legal counsel should review whether the API terms differ from the dump license for your use case.

### On-chain data sources

**Helius** (helius.dev/docs) provides the richest API for Solana data collection. The free tier includes **1M credits/month at 10 RPS** — sufficient for fetching transaction logs, enhanced transaction data, and program IDLs. Sign up at dashboard.helius.dev/signup. The Enhanced Transaction API parses raw transactions into human-readable format with types, descriptions, and decoded account data. Paid tiers start at $49/month (10M credits).

For **Anchor IDL fetching**, use `anchor idl fetch <PROGRAM_ID> --provider.cluster mainnet` or the TypeScript method `Program.fetchIdl(programId, provider)`. IDLs are stored on-chain at PDAs derived from the program ID. The **OtterSec verification API** at `verify.osec.io/status-all/{programId}` provides a registry used by Solana Explorer and SolanaFM.

**SolanaFM** (docs.solana.fm) offers free API access with rate limits. **Alchemy** provides 30M free Compute Units/month (~1.1M simple requests). **QuickNode** offers a one-month free trial only.

### Data processing: deduplication and quality filtering

**datasketch** (`pip install datasketch`, github.com/ekzhu/datasketch) implements MinHash LSH for near-duplicate detection. Use 128 permutations with a Jaccard threshold of 0.8, creating word-level 3-shingles. This is the same approach used by SlimPajama and other major LLM training pipelines. For large corpora, datasketch supports Redis backends and insertion sessions for bulk operations.

**KenLM** (github.com/kpu/kenlm) trains n-gram language models for perplexity-based quality filtering. Installation requires C++ build tools: `sudo apt-get install build-essential cmake libboost-all-dev && pip install https://github.com/kpu/kenlm/archive/master.zip`. Pre-trained Wikipedia English models are available at **huggingface.co/edugp/kenlm** — score web-scraped text against these to filter by quality (low perplexity = resembles clean Wikipedia text).

For Rust code validation, invoke **rustfmt** via stdin (zero temp files, fast syntax check) and **cargo check** via subprocess for full type-checking. Cache a persistent Cargo project directory, swap `src/main.rs` between checks, and set `CARGO_TARGET_DIR` to a shared location to avoid re-downloading dependencies.

### Synthetic data generation

**OpenAI Batch API** is the most cost-effective approach. **GPT-4o-mini batch pricing is $0.075 input / $0.30 output per million tokens** — a 50% discount off standard rates. Submit JSONL files (up to 50,000 requests, 200MB) via the Files API, with results returned within 24 hours. Documentation: **platform.openai.com/docs/guides/batch**. For higher quality, GPT-4o batch runs at $1.25/$5.00 per MTok.

**Anthropic's Message Batches API** (platform.claude.com/docs/en/build-with-claude/batch-processing) offers the same **50% discount** on Claude Sonnet 4 ($1.50/$7.50 per MTok batch), with up to 10,000 queries per batch. Combining batch + prompt caching yields up to **95% savings**.

The most relevant synthetic data methodologies for code are **OSS-Instruct** (Magicoder — use real Solana code snippets as seeds), **Evol-Instruct** (WizardCoder — iteratively evolve coding tasks for increasing complexity), and **GLAN** (systematic taxonomy-based generation covering all Solana development topics). Key resource: **github.com/wasiahmad/Awesome-LLM-Synthetic-Data**.

### Existing Solana datasets on HuggingFace

**Lumo Labs** has published the most comprehensive Solana instruction datasets:

| Dataset | Size | URL |
|---|---|---|
| **Lumo-Fart-DS-Instruct** | ~500K entries | huggingface.co/datasets/lumolabs-ai/Lumo-Fart-DS-Instruct |
| **Lumo-Novel-DS-Instruct** | 95.1K entries | huggingface.co/datasets/lumolabs-ai/Lumo-Novel-DS-Instruct |
| **Lumo-Iris-DS-Instruct** | 28,518 Q&A pairs | huggingface.co/datasets/lumolabs-ai/Lumo-Iris-DS-Instruct |
| **Lumo-8B-DS-Instruct** | 5,502 Q&A pairs | huggingface.co/datasets/lumolabs-ai/Lumo-8B-DS-Instruct |

Other relevant datasets include **almanax/insecure-solana-programs** (curated vulnerability examples), **gaianet/learn-rust** (Rust Q&A pairs), and **ammarnasr/the-stack-rust-clean** (clean Rust code from The Stack). No large-scale Solana code-generation instruction dataset exists yet — this is a clear gap and opportunity.

### License compliance

All training data must carry a verified license. Key decisions by source:

- ✅ **Apache 2.0 repos** (Anchor, SPL, Agave, program-examples): Use freely for training and RAG.
- ❌ **Stack Exchange dump**: **Exclude from training** — the data dump license explicitly prohibits LLM training as of July 2024, and recent dumps include watermarking/data poisoning. Use in RAG retrieval only.
- ⚠️ **Helius/Metaplex docs**: Email for explicit training permission before inclusion. Default to RAG-only until written consent is received.
- ⚠️ **Lumo datasets**: Verify each dataset's HuggingFace license card individually before training inclusion.
- ✅ **Synthetic data** (GPT-4o/Claude generated): Generally permissible per provider ToS for model training.

**Implementation**: Add a `license` field to every record in the data pipeline (see Phase 1.5). Any source with unclear or unverified licensing defaults to **RAG-only** (retrieval at inference time, not included in training data). Maintain a `licenses.csv` tracking: source name, license type, verification date, training-permitted (yes/no/pending), and contact person for permission requests.

---

## Phase 1.5: Data pipeline architecture

A standardized pipeline ensures reproducibility, quality, and legal compliance across all data sources.

### Stage 1 — Collection and schema

All sources are normalized into a standard intermediate JSONL format:

```json
{
  "id": "sha256-of-content",
  "source": "github/solana-foundation/anchor",
  "source_type": "code|docs|qa|synthetic",
  "content": "...",
  "language": "rust|ts|md",
  "license": "Apache-2.0",
  "metadata": {
    "anchor_version": "0.30.1",
    "file_path": "programs/token/src/lib.rs",
    "collected_at": "2026-03-25"
  }
}
```

Store as JSONL files partitioned by source (one directory per source). Track data lineage with **DVC** (dvc.org) using Akash persistent storage or a free-tier Backblaze B2 bucket as the DVC remote. Every pipeline stage is a DVC stage in `dvc.yaml`, enabling `dvc repro` to rebuild from any point.

### Stage 2 — Deduplication

Three-layer deduplication with priority-based conflict resolution:

1. **Exact dedup**: SHA-256 hash of normalized content (strip whitespace/comments for code before hashing).
2. **Near-dedup**: datasketch MinHash LSH with 128 permutations, word-level 3-shingles, Jaccard threshold 0.8.
3. **Priority ordering** when near-duplicates conflict: hand-curated examples > Lumo datasets > scraped docs > synthetic data. Keep the highest-priority version.

Expected reduction: **20–40%** of total collected data. Log dedup statistics per source for the dataset card.

### Stage 3 — Quality filtering

- **Rust code**: `rustfmt` syntax check (fast, catches parse errors) → `cargo check` type check (slower, catches semantic errors). Cache a persistent Cargo project with `CARGO_TARGET_DIR` set to avoid dependency re-downloads.
- **Documentation**: KenLM perplexity filtering — remove documents above the 95th percentile (incoherent or boilerplate text).
- **Length filter**: Discard entries shorter than 50 tokens or longer than 32K tokens.
- **Anchor version tagging**: Parse `Cargo.toml` for `anchor-lang` version. Tag every code record with its Anchor version. **Upweight Anchor 0.30+ patterns by 2–3x** in the final training mix. Add **50–100 migration examples** (old `coral-xyz`/`declare_id!` → new `solana-foundation`/`declare_program!` conversion pairs).
- **Format conversion**: Transform to CPT format (`{"text": "..."}`) for continued pretraining or ChatML SFT format (`{"messages": [...]}`) for instruction tuning.

### Stage 4 — Versioning and publishing

Use semantic versioning: `slm-data-v0.1.0`, `slm-data-v0.2.0`, etc. Each version includes:

- Total record count, per-source breakdown, dedup reduction percentage
- License audit summary (all records have verified `license` field)
- Sample quality spot-check results (50 random samples manually reviewed)
- HuggingFace Hub dataset card with full provenance documentation

Publish to HuggingFace Hub as a versioned dataset. Pin the exact dataset version in training configs for reproducibility.

---

## Phase 2: Model selection, training, and evaluation

### Base model comparison and recommendation

**Primary: Qwen3-Coder-30B-A3B-Instruct** (huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct). This MoE model has 30.5B total parameters but only **3.3B active per token** (8 of 128 experts), delivering "30B-quality" reasoning at "3B-level" compute. Key specs: **262K context window**, Apache 2.0 license, native function calling, ChatML template, **17.5GB VRAM for QLoRA** via Unsloth. SWE-bench Verified score of ~51.6%. Released July 2025, with 619K+ monthly downloads and 125 community quantizations already on HuggingFace.

**Backup: Qwen2.5-Coder-7B-Instruct** (huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct). Dense 7.6B model with **HumanEval 84.1**, 131K context, Apache 2.0, and only **6–8GB VRAM for QLoRA** (fits free Colab T4). Pre-quantized Unsloth version available at `unsloth/Qwen2.5-Coder-7B-Instruct-bnb-4bit`. This is the safest fallback if MoE fine-tuning proves problematic.

**Not recommended**: StarCoder2-7B (too old, 16K context, HumanEval only 35.4, not instruction-tuned, no Unsloth support). DeepSeek-Coder-V2-Lite-Instruct (superseded, restrictive license). Devstral Small 24B (dense architecture requires more VRAM than the MoE alternative for less total knowledge).

### Unsloth: the primary training framework

**GitHub**: github.com/unslothai/unsloth | **Docs**: docs.unsloth.ai | **Install**: `pip install unsloth`

Unsloth delivers **2–2.7x faster** training and **50–75% less VRAM** than standard HuggingFace Transformers, verified independently by HuggingFace's own benchmarks across 59 runs. For MoE models specifically, Unsloth achieves **12x faster** training with **35%+ less VRAM**. Zero accuracy degradation — the speedup comes from hand-written Triton kernels and a manual backprop engine.

**Qwen3-Coder is fully supported.** Dedicated documentation exists at docs.unsloth.ai/docs/models/qwen3-how-to-run-and-fine-tune. A Colab notebook for Qwen2.5-Coder-14B is at the Unsloth blog (unsloth.ai/blog/qwen-coder). The Docker image (`docker pull unsloth/unsloth`) comes pre-installed with all notebooks.

**LoRA configuration for Solana fine-tuning:**

```python
model = FastLanguageModel.get_peft_model(
    model,
    r=16,                    # Rank (16 for SFT, 256 for continued pretraining)
    lora_alpha=16,           # Scaling factor (typically equal to r)
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    lora_dropout=0,          # Optimized by Unsloth
    use_gradient_checkpointing="unsloth",  # 30% less VRAM
    use_rslora=False,        # Enable for continued pretraining
)
```

**Critical MoE fine-tuning notes**: Do NOT fine-tune the router layer (Unsloth disables this by default for stability). The full 16-bit model must download first, then convert to 4-bit on-the-fly. Set context length to 32K for training (262K risks OOM). For continued pretraining, add `embed_tokens` and `lm_head` to target_modules and use higher rank (256) with RSLoRA enabled.

**Continued pretraining vs SFT**: CPT uses `UnslothTrainer` with raw text (`{"text": "..."}` column), standard causal LM objective. SFT uses `SFTTrainer` from TRL with conversation format (`{"messages": [...]}` column). CPT first on raw Solana code/docs, then SFT on instruction pairs.

**Merging and exporting**: `model.save_pretrained_merged("output", tokenizer, save_method="merged_16bit")` creates a standard HuggingFace checkpoint. Push to Hub with `model.push_to_hub_merged(...)`. Export GGUF for Ollama with `model.push_to_hub_gguf(..., quantization_method="q4_k_m")`.

### LLaMA-Factory as backup

**GitHub**: github.com/hiyouga/LLaMA-Factory (ACL 2024). Key advantage: a mature Web UI (LLaMA Board) via `llamafactory-cli webui` and stronger multi-GPU/DeepSpeed integration. Key disadvantage: no custom Triton kernels, so training is ~2x slower than Unsloth with 50–75% more VRAM. Use if Unsloth encounters compatibility issues with specific model configurations.

### Training data formats

Unsloth expects **ChatML format** with a `messages` column for SFT:

```json
{"messages": [
  {"role": "system", "content": "You are a Solana/Anchor expert."},
  {"role": "user", "content": "How do I create a PDA?"},
  {"role": "assistant", "content": "In Anchor, you derive a PDA using seeds..."}
]}
```

For ShareGPT-format data (common in community datasets), Unsloth provides `standardize_sharegpt()` to convert. The Alpaca format (`instruction`/`input`/`output` keys) is best for single-turn tasks and easily converts to ChatML.

### Evaluation: Solana Bench and beyond

**Solana Bench** (github.com/solana-foundation/solana-gym-env, announced at solana.com/news/solana-bench) is THE benchmark for Solana LLM operational competence. It tests the ability to compose valid transactions, choose accounts correctly, use SDKs, recover from errors, and explore breadth across Solana programs. Two environments: Basic (foundational SDKs) and Swap (DeFi-focused). Models tested include GPT-5, Claude Sonnet 4, and Gemini 2.5 Flash.

Run it with: `git clone https://github.com/solana-foundation/solana-gym-env && uv sync && uv run python code_loop_explorer.py`. Full model comparison costs ~$150–200. The Solana Foundation is **actively funding** open-source research on expanding these benchmarks.

Additional evaluation tools: **CodeBERTScore** (`pip install code-bert-score`, github.com/neulab/code-bert-score) is more correlated with functional correctness than BLEU for code evaluation. **EleutherAI's lm-evaluation-harness** (github.com/EleutherAI/lm-evaluation-harness, 11.2K+ stars) supports 200+ tasks including HumanEval and MBPP. **MT-Bench** (github.com/lm-sys/FastChat) provides GPT-4 as judge with >80% human agreement. For RAG-specific evaluation, **DeepEval** (`pip install deepeval`) includes hallucination detection and RAG metrics.

### Evaluation protocol

A three-phase evaluation framework ensures measurable progress and prevents regressions.

**Phase A — Baseline (Week 2):**

Run the unmodified Qwen3-Coder-30B-A3B through all evaluation suites before any fine-tuning:

- **Solana Bench** (Basic + Swap environments) — establishes Solana-specific competence baseline
- **HumanEval + MBPP** via `lm-evaluation-harness` — general coding regression guards
- **Custom Solana eval set (80+ tasks):**
  - 15 PDA derivation tasks
  - 15 Anchor constraint tasks
  - 10 SPL token operations
  - 10 CPI (cross-program invocation) tasks
  - 10 error handling tasks
  - 10 Asymmetric Research adversarial prompts (debunked vulnerability patterns)
  - 10 transaction construction tasks
  - Each task includes: input prompt, reference solution, scoring rubric (compilable? correct? secure?)
  - Score via `cargo check` pass rate + CodeBERTScore against reference solutions

**Phase B — Checkpoint evaluation (every 500 training steps):**

- Fast subset only: 50 custom Solana tasks + HumanEval (~30 min per checkpoint)
- Log all metrics to W&B via a custom `TrainerCallback` that triggers eval at step intervals
- Track: loss curve, eval pass rate, CodeBERTScore mean, and `cargo check` pass rate

**Phase C — Acceptance criteria (must pass before deployment):**

| Metric | Target |
|---|---|
| Solana Bench (Basic + Swap) | ≥15% improvement over baseline |
| HumanEval / MBPP | ≤2 point regression from baseline |
| Adversarial prompts (Asymmetric Research) | ≥90% correct refusal rate |
| Custom Solana eval `cargo check` pass rate | ≥70% |

If acceptance criteria are not met after SFT, iterate on data quality (not hyperparameters) first — data issues are the most common cause of underperformance.

### Alignment and safety strategy

The Asymmetric Research misinformation report identifies six specific vulnerability classes that LLMs commonly hallucinate about Solana. The alignment strategy addresses this in three layers.

**Layer 1 — System prompt guardrails (zero cost, deploy immediately):**

Hard-coded rules prepended to every inference request via the API gateway:

- Never suggest reentrancy guards (Solana prevents reentrancy via CPI depth limits)
- Never warn about closed account discriminator attacks (fixed in Anchor ~3 years ago)
- Never suggest float non-determinism concerns (LLVM-emulated, fully deterministic on Solana)
- Never reference `load_instruction_at` (deprecated — use `get_instruction_relative`)
- Default to Anchor 0.30+ patterns (`declare_program!`, `solana-foundation/anchor`)
- State uncertainty explicitly rather than guessing on security-sensitive questions

**Layer 2 — DPO alignment training (Week 7–8):**

Create **200–400 preference pairs** from the 6 debunked vulnerability classes:
- "Chosen" response: correct Solana security guidance
- "Rejected" response: the hallucinated vulnerability warning

Run DPO after SFT using TRL's `DPOTrainer` with Unsloth. Alternative: **ORPO** (combines SFT + alignment in a single training step, saving time). DPO training requires ~2–4 hours on A100 for this dataset size.

**Layer 3 — Runtime output filtering (safety net):**

Post-processing middleware in FastAPI that scans model outputs for known-bad patterns:
- Reentrancy guard suggestions → append correction footnote
- `coral-xyz` import references → suggest `solana-foundation/anchor` instead
- Deprecated API usage (`load_instruction_at`, old `declare_id!` patterns) → append migration note

This is a last-resort safety net, not a substitute for proper training alignment.

---

## Phase 3: Inference serving and RAG pipeline

### SGLang for high-throughput inference

**GitHub**: github.com/sgl-project/sglang (25K+ stars) | **Docs**: docs.sglang.io | **Install**: `pip install "sglang[all]"`

SGLang consistently outperforms vLLM by **15–30% on throughput** in independent benchmarks, with particular advantages for multi-turn conversations via its RadixAttention prefix caching (automatic, tree-based KV cache reuse). Used in production by Cursor, xAI, and NVIDIA.

**Deploy a quantized Qwen3-Coder-30B-A3B in Docker:**

```bash
docker run --gpus all --shm-size 32g -p 30000:30000 \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  --env "HF_TOKEN=your_token" --ipc=host \
  lmsysorg/sglang:latest \
  python3 -m sglang.launch_server \
    --model-path your-org/slm-qwen3-coder-awq \
    --host 0.0.0.0 --port 30000 \
    --api-key your-secret-key \
    --mem-fraction-static 0.85
```

This exposes an OpenAI-compatible API at `/v1/chat/completions` with full streaming support. SGLang supports AWQ, GPTQ, GGUF, FP8, and FP4 quantization. For MoE models, **AWQ 4-bit** provides ~92–95% of FP16 quality on HumanEval while cutting VRAM to ~17GB. Pre-quantize with AutoAWQ (`pip install autoawq`).

vLLM (github.com/vllm-project/vllm, docs.vllm.ai) serves as backup with a more mature API ecosystem and broader hardware support. Deploy with: `docker run --gpus all vllm/vllm-openai:latest --model your-model`.

### Qdrant vector database

**Docs**: qdrant.tech/documentation | **Docker**: `docker run -p 6333:6333 -p 6334:6334 -v $(pwd)/qdrant_storage:/qdrant/storage qdrant/qdrant`

For 50K–100K document chunks with 384-dimensional vectors, Qdrant requires approximately **500MB–1GB** total storage including HNSW index overhead and payloads. A 2GB Docker container on the Akash CPU instance handles this comfortably.

Qdrant supports **hybrid search** combining dense vectors with BM25-style sparse vectors using Reciprocal Rank Fusion. Configure with named vector fields and `SparseVectorParams(modifier=Modifier.IDF)`. The Python client (`pip install qdrant-client`, v1.17.1) supports both sync and async operations. Enable gRPC (`prefer_grpc=True`) for 2–3x throughput improvement. The free Qdrant Cloud tier provides 1GB without a credit card.

### Embedding and reranking models

For the embedding model, start with **BAAI/bge-small-en-v1.5** (384-dim, 33M params, MIT license, huggingface.co/BAAI/bge-small-en-v1.5) for fast iteration. For better code retrieval, upgrade to **Qwen3-Embedding-0.6B** — ranked #1 on MTEB-Code benchmark, instruction-aware, with flexible dimensionality (32–1024), Apache 2.0. Use the **sentence-transformers** library (v5.3.0): `pip install sentence-transformers`.

For reranking, **cross-encoder/ms-marco-MiniLM-L-6-v2** (22.7M params) is the lightweight baseline. For production, **BAAI/bge-reranker-v2-m3** (568M params, 100+ languages) or **Jina Reranker v2** (278M params, 15x faster, includes code search) are superior. The reranking pattern: retrieve 20–50 documents from Qdrant, rerank down to 5–10 for the LLM context. This adds 200–500ms latency but improves accuracy by **20–35%**.

### RAG architecture — lightweight custom pipeline

Skip heavy frameworks for a $10K project. Build a minimal pipeline:

```python
# Embed query → Search Qdrant → Format context → Call LLM
embedder = SentenceTransformer("BAAI/bge-small-en-v1.5")
qdrant = QdrantClient(url="http://localhost:6333")

query_vector = embedder.encode(query, normalize_embeddings=True).tolist()
results = qdrant.search("solana_docs", query_vector=query_vector, limit=20)
# Rerank with cross-encoder, take top 5
context = "\n\n".join([r.payload["text"] for r in reranked[:5]])
# Call SGLang with context-augmented prompt
```

If the project later needs hybrid search, LlamaIndex (developers.llamaindex.ai, `pip install llama-index llama-index-vector-stores-qdrant`) provides native Qdrant hybrid integration with `vector_store_query_mode=HYBRID`. Useful tutorials: qdrant.tech/documentation/tutorials-build-essentials/rag-deepseek/ and blog.futuresmart.ai/building-rag-applications-without-langchain-or-llamaindex.

For **chunking**, use AST-based splitting (tree-sitter) for Rust code files at function/class boundaries, and recursive character splitting at 256–512 tokens with 10–20% overlap for documentation prose. This dual strategy respects code structure while maintaining context in documentation.

### Context window management

The model's 262K context window does not mean all of it should be used — quality degrades beyond the 32K training distribution. Allocate the 32K effective budget as follows:

| Segment | Token Budget |
|---|---|
| System prompt (guardrails + version info) | 500 |
| RAG context (top 5 retrieved docs) | 6,000 |
| Conversation history (4–6 turns) | 8,000 |
| Current user message | 4,000 |
| Reserved for generation | ~13,500 |

**Dynamic rebalancing**: If the user pastes large code blocks (>4K tokens), reduce RAG context to 3K and conversation history to 5K to maintain generation headroom. Use the Qwen3-Coder tokenizer for token counting in the API gateway (`from transformers import AutoTokenizer; tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3-Coder-30B-A3B-Instruct")`) — do NOT use `tiktoken`, which is OpenAI-specific and will produce inaccurate counts for Qwen's vocabulary. Cache the tokenizer locally for fast CPU-only counting.

**VS Code version detection**: Read the user's `Cargo.toml` for `anchor-lang` version and inject the detected version into the system prompt segment. This enables version-aware responses without consuming RAG budget.

---

## Phase 4: VS Code extension, CLI tool, and API layer

### FastAPI backend with OpenAI-compatible streaming

Build the API gateway in FastAPI with SSE streaming. The core pattern: a `/v1/chat/completions` endpoint that proxies to SGLang, adding RAG context injection and safety filtering (see Alignment Layer 3 in Phase 2).

### API authentication and security

**TLS termination**: **Caddy** reverse proxy with automatic Let's Encrypt certificate provisioning ($0 cost). Caddy handles HTTPS, HTTP/2, and certificate renewal automatically. Add IP-based rate limiting at the Caddy layer as the first line of defense.

**API gateway**: Use **LiteLLM Proxy** (github.com/BerriAI/litellm) as the primary API gateway rather than building custom auth. LiteLLM provides:
- Virtual API keys with per-key budget and rate limits
- Usage tracking and spend monitoring per key
- SQLite backend (sufficient for MVP scale)
- OpenAI-compatible passthrough to SGLang
- Admin API for key management and rotation

**Rate limit tiers:**

| Tier | Requests/min | Tokens/day | Use case |
|---|---|---|---|
| Free | 10 | 50K | Community / evaluation |
| Standard | 30 | 500K | Active developers |
| Admin | 100 | Unlimited | Team members |

**Abuse prevention**: Three layers — IP rate limiting at Caddy → per-key limits at LiteLLM → auto-suspend keys exceeding 10x their daily budget. Token rotation: 90-day expiry, regeneration via LiteLLM admin API.

**Free-tier signup friction**: Require GitHub OAuth for API key issuance (verifies real developer identity at zero cost). Limit to one key per GitHub account. For the VS Code extension, embed a hardcoded "anonymous" key with strict limits (5 req/min, 10K tokens/day) for frictionless onboarding, then prompt users to authenticate with GitHub for Standard tier access.

### VS Code extension

**Official API docs**: code.visualstudio.com/api | **Scaffold**: `npm install -g yo generator-code && yo code`

The extension needs three core capabilities: a sidebar chat panel (Webview API), code actions for error explanation, and rust-analyzer integration.

**Sidebar chat**: Register a `WebviewViewProvider` in the activity bar, implement two-way messaging with `webview.postMessage()` / `webview.onDidReceiveMessage()`, and stream LLM responses chunk-by-chunk from the extension host to the webview DOM.

**Code actions** ("Explain with SLM"): Implement a `CodeActionProvider` that filters `context.diagnostics` for rust-analyzer errors and offers quick-fix actions. Register with `vscode.languages.registerCodeActionsProvider({ language: "rust" }, provider)`.

**Rust-analyzer error interception**: Subscribe to `vscode.languages.onDidChangeDiagnostics`, read errors with `getDiagnostics(uri)`, and filter for diagnostics with source `"rust-analyzer"`.

**Publishing**: Create an Azure DevOps PAT, register as a publisher at marketplace.visualstudio.com/manage, package with `vsce package`, publish with `vsce publish`. For Open VSX (VSCodium users), use `ovsx publish`.

**Reference implementations**: **Continue.dev** (github.com/continuedev/continue) has a three-part architecture (core TypeScript, React sidebar UI, VS Code extension) communicating via message passing. **Cody** by Sourcegraph (github.com/sourcegraph/cody-public-snapshot, Apache 2.0) provides another production-grade reference for chat, autocomplete, and inline edit features.

### Latency budget and SLA targets

Concrete performance targets for a usable developer experience:

| Component | Target Latency |
|---|---|
| RAG embedding (bge-small on CPU) | 30ms |
| Qdrant vector search (50K vectors, HNSW) | 10ms |
| Reranker (MiniLM-L-6 on CPU) | 200ms |
| Time to first token (SGLang + prefix caching) | 100ms |
| **Total TTFT (quality mode)** | **~440ms** |
| Token generation speed | 50 tok/s |
| Full 500-token response | ~10.4s |

**Two quality tiers:**

- **`fast` mode** (for code actions, inline completions): Skip reranking, top-5 vector search only. TTFT ~240ms.
- **`quality` mode** (for chat panel, complex queries): Full reranking pipeline. TTFT ~440ms.

Streaming is mandatory for both tiers. Monitor p50/p95/p99 latencies via structured logging. Alert if TTFT p95 exceeds 1s. The VS Code extension should default to `fast` mode for code actions and `quality` mode for chat.

### Python CLI tool (MVP)

Ship a **Python CLI** first using `typer` + `httpx` + `rich` (~200–300 lines). This saves 1–2 weeks compared to a Rust CLI for equivalent functionality at MVP stage:

```
slm chat "How do I create a PDA?"
slm explain --tx <signature>
slm explain --error 0x1771
```

Install via `pip install slm-cli` or `pipx install slm-cli`. Uses `httpx` with SSE streaming for real-time token output and `rich` for formatted terminal display.

### Rust CLI tool (post-MVP stretch goal)

Build with **clap** (crates.io/crates/clap, v4.6, 725M+ downloads). Use the derive API for clean subcommand definition: `slm explain --error-code 0x1771`, `slm chat --message "..."`, `slm tx --signature "..."`. Stream responses from the API using **reqwest** with the `stream` feature (`reqwest = { version = "0.13", features = ["stream", "json"] }`) and process SSE chunks via `futures_util::StreamExt`.

Publish to crates.io (`cargo publish`) and distribute via npm using platform-specific packages (`@slm/cli-linux-x64`, `@slm/cli-darwin-arm64`) with a base package containing a Node.js shim. The blog post at **blog.orhun.dev/packaging-rust-for-npm/** provides the definitive guide.

### Solana error explanation integration

Parse transaction logs from Helius's enhanced transaction API (`POST https://api-mainnet.helius-rpc.com/v0/transactions/?api-key=KEY`). Transaction logs follow patterns like `"Program <ID> failed: custom program error: 0x<HEX>"`. Convert hex to decimal, then look up the error in the program's Anchor IDL. Anchor error numbering: 0–99 internal, 100–4999 framework (e.g., `ConstraintMut` = 2000), **6000+ custom errors** (subtract 6000 to get the variant index in the `#[error_code]` enum). Fetch IDLs with `anchor idl fetch <PROGRAM_ID>` or from the OtterSec verification API.

### Fallback and graceful degradation

- **API level**: 5-second timeout on SGLang inference → return "temporarily unavailable" message alongside RAG-retrieved docs (useful context without LLM generation).
- **Local fallback**: Publish a Q4_K_M GGUF quantization to HuggingFace → users pull via `ollama pull slm-solana` → VS Code extension setting "Fallback to local Ollama" routes requests to `localhost:11434` when the remote API is unreachable. **Build the GGUF during model export** (Phase 2): `model.push_to_hub_gguf("your-org/slm-solana-gguf", tokenizer, quantization_method="q4_k_m")`, then create an Ollama Modelfile with the system prompt baked in. Test the local fallback path before launch.

### Testing strategy

- **Unit tests (pytest)**: RAG chunking correctness, embedding dimension validation, Qdrant operations (`:memory:` client), format conversion between pipeline stages, API request/response validation.
- **Integration tests**: End-to-end RAG retrieval (query → embed → search → rerank → format), API streaming round-trip (SSE chunks arrive correctly), VS Code extension (`@vscode/test-electron`).
- **Model regression tests**: Custom eval set from the evaluation protocol + CodeBERTScore on 20 golden reference outputs per model version. Run before any deployment.

### CI/CD pipeline

- **Training pipeline**: Makefile stages (`make collect → dedup → prepare → train → eval → export`), DVC for data artifact tracking and reproducibility.
- **Inference deployment**: GitHub Actions → Akash CLI redeploy with new model weights → restart SGLang → smoke test (5 canonical prompts, assert valid streamed responses) → automatic rollback on failure.
- **RAG updates**: Weekly cron job re-embeds updated docs/code from monitored repositories, upserts new vectors to Qdrant, logs update statistics.

### Backup and disaster recovery

The Akash CPU instance hosts critical stateful data (Qdrant vectors, SQLite feedback DB, API keys, Caddy config). Akash providers can go offline, so offsite backups are essential.

- **Daily automated backups**: Cron job at 03:00 UTC runs `qdrant-client` snapshot export + SQLite `.backup` command → compress → upload to a free-tier Backblaze B2 bucket (10GB free) or HuggingFace private dataset repo (zero cost).
- **Weekly offsite**: Push compressed backup to a second location for redundancy.
- **Recovery time target**: Full restore from backup in <1 hour. Document the restore procedure in `docs/disaster-recovery.md` and test it once before launch.
- **Model weights**: Always stored on HuggingFace Hub (the source of truth). Inference nodes pull from Hub on deploy — no need to back up model files separately.

### Post-launch retraining plan

Anchor and Solana evolve continuously. The fine-tuned model weights will go stale within 3–6 months without retraining.

- **Trigger criteria**: Major Anchor version release (e.g., 0.31), new Solana runtime features, or custom eval pass rate dropping below acceptance thresholds on updated test cases.
- **Data refresh cycle**: Monthly — re-run the data collection pipeline against monitored repos, generate new synthetic pairs for any new APIs/features, run dedup against existing training data, publish as a new dataset version.
- **Retraining cadence**: Quarterly SFT refresh (or sooner if triggered). Budget ~$50–100 per retraining run on Akash A100.
- **DPO from user feedback**: After accumulating 200+ rated responses, create new preference pairs from thumbs-up/down data (with human review). Run DPO on top of the latest SFT checkpoint.

### Monitoring and observability

- **Structured logging**: `structlog` in FastAPI, output as JSONL, daily log rotation on the Akash CPU instance.
- **Health endpoint**: `/health` checks SGLang responsiveness + Qdrant connectivity + disk space. Used by UptimeRobot.
- **Uptime monitoring**: UptimeRobot free tier (50 monitors, 5-min check intervals) for the API endpoint and health check.
- **GPU monitoring**: `nvidia-smi` metrics via cron → alert to Discord webhook if GPU utilization drops to 0% or VRAM exceeds 95%.
- **Hallucination tracking**: Weekly manual review of 50 sampled responses + DeepEval automated hallucination scoring.

### User feedback loop

- **Collection**: Thumbs-up/down buttons in VS Code sidebar + single-keypress rating in CLI (`slm` prints "Was this helpful? [y/n]").
- **Storage**: SQLite on Akash CPU instance, schema: `(id, query, response, rating, timestamp, user_hash)`.
- **Review cadence**: Weekly — sort by negative ratings, identify recurring failure patterns.
- **Post-MVP alignment**: Negatively-rated responses → DPO "rejected" examples, positively-rated → DPO "chosen" examples. Human review required before inclusion in training data.

### Cost tracking

- **Compute**: Akash dashboard tracks credit consumption natively. Set alerts at 50% and 80% credit usage.
- **Synthetic data APIs**: Hard spending limits — OpenAI dashboard ($500 cap), Anthropic dashboard ($300 cap).
- **Inference API spend**: LiteLLM Proxy tracks per-key API usage automatically (see API authentication section).
- **Budget reviews**: Weekly Google Sheets update with actual vs. planned spend per category.

---

## Phase 5: Grant funding and community strategy

### The SLM RFP — an immediate, untapped opportunity

The Solana Foundation posted an RFP for a "Solana Language Model" on **forum.solana.com/t/request-for-proposal-rfp-solana-language-model/4631** on February 2, 2026, posted by user "rajgokaI." As of research time, the post has **zero replies** — no competing proposals or discussion threads. The RFP calls for AI infrastructure that understands Solana at protocol, developer, and application levels, with objectives spanning developer productivity, network intelligence, secure AI integration, and ecosystem applications. This is not a fixed-amount grant but likely involves significantly larger funding than standard grants given the infrastructure scope.

### Multi-track funding strategy

Apply simultaneously to multiple sources:

- **Superteam India Instagrants** (earn.superteam.fun/grants/Solana-fdn-coindcx-instagrant/): Up to **$15,000 USDC**, 48–72 hour decision, India-only. $698.5K already approved to 173 recipients. Developer tooling is an explicitly funded category. Contact: aditya@adityashetty.xyz.

- **Solana Foundation Direct Grants** (solana.org/grants-funding, application form at share.hsforms.com/1GE1hYdApQGaDiCgaiWMXHA5lohw): Milestone-based grants, ~4 week review cycle. The Foundation has deployed **$100M+ to 500+ projects** and explicitly identifies developer tooling as "vital to Solana's health and growth." Convertible grants available for projects with commercial potential.

- **Colosseum Spring 2026 Hackathon** (colosseum.com): **April 6 – May 11, 2026** — aligns perfectly with the 14-week timeline. Winners can raise **$250,000** from Colosseum's venture fund. The Eternal Challenge also provides perpetual rolling competition with $25K awards.

- **LamportDAO Microgrants** (in.superteam.fun/instagrants/lamportdao-grants-program): $1–$5K monthly grants that serve as **signal amplifiers** — recipients often get recommended to the Solana Foundation for larger funding.

---

## Cross-cutting references every SLM builder needs

### The Asymmetric Research misinformation report

Published March 12, 2026 at **blog.asymmetric.re/solana-vulnerabilities-that-arent-unpacking-common-misreports/**, this report identifies exactly where LLMs fail on Solana security. It debunks six commonly hallucinated "vulnerability" classes: reentrancy (not practical in Solana due to CPI depth limits), closed account discriminator (fixed in Anchor ~3 years ago), float non-determinism (irrelevant since float ops are emulated by LLVM), self-transfer token bug, deprecated `load_instruction_at`, and partial state commitment. **This document is essential negative training data** — the fine-tuned model must not generate these debunked patterns.

### The awesome-solana-ai ecosystem map

**github.com/solana-foundation/awesome-solana-ai** catalogs every AI tool in the Solana ecosystem: 30+ coding "skills" (curated instruction sets for AI assistants), agent frameworks (SendAI, Eliza, GOAT), MCP servers (including the official Solana Developer MCP at mcp.solana.com), and development tools. The ecosystem is converging on the **MCP + Skills** pattern (Anthropic's Model Context Protocol plus curated reference files), which the SLM should be optimized to work within.

### SendAI Solana Agent Kit

**github.com/sendaifun/solana-agent-kit** (1.6K stars, 810 forks) is the most widely adopted framework connecting LLMs to Solana, with 60+ actions across 30+ protocols via a plugin architecture. The MCP server at github.com/sendaifun/solana-mcp provides onchain tools for Claude AI. A Solana coding LLM should generate code compatible with the Agent Kit's plugin system and tool definitions. Docs: docs.sendai.fun.

### Lumo Labs' existing models and methodology

Lumo Labs has published models from 8B to 70B (huggingface.co/lumolabs-ai), all fine-tuned on Solana Q&A data using LoRA on LLaMA 3.1 bases. Their training approach: chunk documentation into 1500–2000 character segments with overlap, generate 3 Q&A pairs per chunk using GPT-4, fine-tune with standard LoRA configuration (lr=3e-4, batch=1, gradient_accumulation=4). The Lumo-Fart-DS-Instruct dataset (~500K entries) represents the largest existing Solana instruction dataset. These models establish a baseline that the SLM project should aim to significantly exceed.

### Helius AI integration guide

**helius.dev/blog/how-to-use-ai-to-build-solana-apps** explains why AI struggles with Solana (account model confusion, PDA derivation, SDK version confusion) and documents Helius's MCP Server (60+ tools), Skills (expert instruction sets with routing logic), and Claude Code Plugin. The "Skills" concept — curated instruction sets with reference files — maps directly to how a Solana LLM's RAG retrieval system should be structured.

---

## Conclusion: the critical path through 14 weeks

### Two-track execution timeline

**Track 1 — Colosseum Hackathon (April 6 – May 11):**

| Week | Dates | Milestone |
|---|---|---|
| 1 | Mar 25–Apr 1 | Data pipeline v0.1, baseline eval on unmodified Qwen3-Coder, begin CPT |
| 2 | Apr 1–6 | Complete CPT, begin SFT, register for hackathon |
| 3–4 | Apr 6–20 | Complete SFT, deploy to Akash, basic API + VS Code chat panel |
| 5–6 | Apr 20–May 4 | RAG pipeline, eval results, polish demo |
| 7 | May 4–11 | Final submission + demo video |

**Track 2 — RFP response (parallel):** One team member writes the Solana Foundation proposal by April 1, referencing baseline eval results from Week 1.

### Full 14-week roadmap

| Week | Milestone |
|---|---|
| 1–2 | Data pipeline (Phase 1 + 1.5), baseline eval, RFP submission |
| 3–4 | Continued pretraining (CPT) on Solana code/docs |
| 5–6 | SFT on instruction pairs + DPO alignment |
| 7 | Full evaluation suite, iterate on data quality if needed |
| 8–9 | Inference deployment (SGLang on Akash), RAG pipeline, API gateway (LiteLLM) |
| 10–11 | VS Code extension, Python CLI, latency optimization |
| 12 | Integration testing, monitoring setup, feedback loop |
| 13–14 | Documentation, public launch, Superteam grant application |

### Verification plan

1. **Eval suite**: Run baseline eval on unmodified Qwen3-Coder → record scores → compare after fine-tuning → assert acceptance criteria met
2. **Data pipeline**: Run full dedup pipeline → assert 20–40% reduction → spot-check 50 random samples for quality and correct licensing
3. **API**: `curl` the `/v1/chat/completions` endpoint → assert streamed SSE response with valid auth
4. **Safety**: Send all 6 Asymmetric Research adversarial prompts → assert correct refusals (≥90%)
5. **VS Code**: Install extension → open chat panel → send Solana query → verify streamed response with RAG context
6. **CLI**: `slm chat "test"` → verify streamed output with formatting
7. **Latency**: Measure TTFT → assert <500ms in quality mode, <250ms in fast mode

### Key insights

The research reveals three non-obvious insights that should shape execution. First, **the training data gap is the real bottleneck**, not model architecture — Lumo Labs' largest dataset has only 500K entries, and no large-scale code-generation instruction dataset exists for Solana. Investing 4–5 weeks in high-quality data curation (OSS-Instruct from real Anchor programs, Evol-Instruct for progressive complexity, and incorporating the Asymmetric Research corrections as hard negatives) will determine model quality more than any other decision.

Second, **the MoE architecture of Qwen3-Coder-30B-A3B fundamentally changes the economics**. With only 3.3B active parameters, inference runs at 3B-model speeds while accessing 30B of knowledge — meaning an ~$100–150/month Akash RTX 4090 serves the model 24/7 with room to spare. This makes the $10K budget feasible where it would not be with a dense 30B model.

Third, **the SLM RFP on forum.solana.com has zero responses**, and the Colosseum Spring Hackathon starts April 6. Submitting the RFP response immediately while entering the hackathon creates two shots at significant funding in parallel. The Superteam India Instagrants ($15K, 72-hour decision) can bootstrap development costs within the first week. Together, these three funding tracks could potentially cover the project budget and then some, while the Solana Bench evaluation framework provides the objective success metric the Foundation is looking for.