# SLM — Data Pipeline + Training Pipeline
# Usage:
#   Data:     make all | make collect-all | make dedup | make filter | make prepare
#   Training: make train | make cpt | make sft | make dpo | make eval
#   Full:     make pipeline  (data + train + eval)

PYTHON := python3
SCRIPTS := scripts
TRAINING := training

# Training config (override with env vars or make args)
MODEL       ?= Qwen/Qwen3-Coder-30B-A3B
DATA_DIR    ?= /workspace/data
CKPT_DIR    ?= /workspace/checkpoints
GCP_VM      ?= e-man@34.66.138.40
GCP_DATA    ?= ~/slm/data/final

.PHONY: all collect collect-hf crawl-docs crawl-forum collect-se collect-onchain \
        migrate-examples synthetic-oss synthetic-evol synthetic-glan \
        collect-all dedup filter prepare publish stats clean help \
        train cpt sft dpo eval eval-baseline eval-sft eval-compare \
        upload-data prepare-dpo export-gguf export-merged push-hf \
        pipeline gpu-check disk-check clean-checkpoints

# ─── Full pipeline ───────────────────────────────────────────────────────────

all: collect-all dedup filter prepare ## Run the full pipeline (collect → dedup → filter → prepare)

# ─── Stage 1: Collection ─────────────────────────────────────────────────────

collect: ## Clone GitHub repos and normalize to JSONL
	$(PYTHON) $(SCRIPTS)/collect.py

collect-hf: ## Download HuggingFace datasets (Lumo, learn-rust, stack-rust-clean)
	$(PYTHON) $(SCRIPTS)/collect.py collect-hf-datasets

crawl-docs: ## Crawl doc sites (docs.rs, Helius, Metaplex) via Playwright
	$(PYTHON) $(SCRIPTS)/crawl_docs.py

crawl-forum: ## Crawl forum.solana.com via Discourse API
	$(PYTHON) $(SCRIPTS)/crawl_forum.py

collect-se: ## Collect Solana Stack Exchange Q&A (RAG-only)
	$(PYTHON) $(SCRIPTS)/collect_stackexchange.py

collect-onchain-idls: ## Fetch Anchor IDLs via Helius/OtterSec APIs
	$(PYTHON) $(SCRIPTS)/collect_onchain.py idls

collect-onchain-txs: ## Fetch enhanced transactions via Helius API
	$(PYTHON) $(SCRIPTS)/collect_onchain.py transactions

migrate-examples: ## Generate Anchor old→new migration examples
	$(PYTHON) $(SCRIPTS)/migrate_examples.py

collect-all: collect collect-hf crawl-docs crawl-forum collect-se migrate-examples ## Run all collection stages

# ─── Synthetic data generation ───────────────────────────────────────────────

synthetic-oss: ## Generate OSS-Instruct batch requests from code seeds
	$(PYTHON) $(SCRIPTS)/synthetic.py oss-instruct

synthetic-evol: ## Generate Evol-Instruct batch requests (progressive complexity)
	$(PYTHON) $(SCRIPTS)/synthetic.py evol-instruct

synthetic-glan: ## Generate GLAN batch requests (taxonomy-based coverage)
	$(PYTHON) $(SCRIPTS)/synthetic.py glan

synthetic-all: synthetic-oss synthetic-evol synthetic-glan ## Generate all synthetic batch request files

# ─── Stage 2-4: Processing ───────────────────────────────────────────────────

dedup: ## Deduplicate collected data (SHA-256 + MinHash LSH)
	$(PYTHON) $(SCRIPTS)/dedup.py

filter: ## Quality filtering (rustfmt, length, heuristics, Anchor tagging)
	$(PYTHON) $(SCRIPTS)/filter.py

filter-full: ## Quality filtering with all checks (rustfmt + cargo check + KenLM)
	$(PYTHON) $(SCRIPTS)/filter.py --no-skip-cargo --enable-kenlm

prepare: ## Generate CPT and SFT training formats with upweighting
	$(PYTHON) $(SCRIPTS)/prepare.py

# ─── Stage 4b: Publishing ────────────────────────────────────────────────────

publish-dry: ## Dry run: show what would be uploaded to HuggingFace
	$(PYTHON) $(SCRIPTS)/publish.py --repo-id slm-project/slm-data --dry-run

publish: ## Publish dataset to HuggingFace Hub
	$(PYTHON) $(SCRIPTS)/publish.py --repo-id slm-project/slm-data

# ─── Utilities ───────────────────────────────────────────────────────────────

stats: ## Print dataset statistics without regenerating
	$(PYTHON) $(SCRIPTS)/prepare.py --stats-only

list-sources: ## List all configured data sources with license status
	$(PYTHON) $(SCRIPTS)/collect.py --list

list-crawl: ## List configured crawl targets
	$(PYTHON) $(SCRIPTS)/crawl_docs.py --list

clean-processed: ## Remove processed data (keep raw clones)
	rm -rf data/processed/*.jsonl data/deduped/*.jsonl data/final/*.jsonl data/final/*.json

clean: ## Remove all generated data (keep raw clones)
	rm -rf data/processed data/deduped data/final data/synthetic
	mkdir -p data/{processed,deduped,final,synthetic}

clean-all: ## Remove everything including raw clones
	rm -rf data/raw data/processed data/deduped data/final data/synthetic
	mkdir -p data/{raw,processed,deduped,final,synthetic}

install: ## Install all pipeline dependencies
	pip install typer rich datasketch xxhash httpx trafilatura playwright datasets huggingface-hub
	playwright install chromium
	@echo "Optional: pip install https://github.com/kpu/kenlm/archive/master.zip (for KenLM)"

# ═══════════════════════════════════════════════════════════════════════════════
# TRAINING PIPELINE (run on Akash GPU container)
# ═══════════════════════════════════════════════════════════════════════════════

pipeline: all train eval ## Full pipeline: data prep → train → eval

train: cpt sft dpo ## Run all training stages (CPT → SFT → DPO)

# ─── Data upload (to Akash container) ───────────────────────────────────────

upload-data: ## SCP training data from GCP VM to Akash container
	mkdir -p $(DATA_DIR)
	scp $(GCP_VM):$(GCP_DATA)/cpt_train.jsonl $(DATA_DIR)/
	scp $(GCP_VM):$(GCP_DATA)/sft_train.jsonl $(DATA_DIR)/
	scp $(GCP_VM):$(GCP_DATA)/dataset_meta.json $(DATA_DIR)/
	scp $(GCP_VM):~/slm/data/processed/dpo-chosen*.jsonl $(DATA_DIR)/ 2>/dev/null || true
	scp $(GCP_VM):~/slm/data/processed/dpo-rejected*.jsonl $(DATA_DIR)/ 2>/dev/null || true
	scp $(GCP_VM):~/slm/data/synthetic/dpo-chosen*.jsonl $(DATA_DIR)/ 2>/dev/null || true
	scp $(GCP_VM):~/slm/data/synthetic/dpo-rejected*.jsonl $(DATA_DIR)/ 2>/dev/null || true
	@echo "✓ Data uploaded to $(DATA_DIR)"

prepare-dpo: ## Merge DPO chosen/rejected files into single JSONL files
	$(PYTHON) $(TRAINING)/prepare_dpo.py --data-dir $(DATA_DIR) --output-dir $(DATA_DIR)

# ─── Stage 1: Continued Pre-Training ───────────────────────────────────────

cpt: ## Stage 1: Continued Pre-Training on Solana corpus
	$(PYTHON) $(TRAINING)/train_cpt.py \
		--model_name $(MODEL) \
		--data_path $(DATA_DIR)/cpt_train.jsonl \
		--output_dir $(CKPT_DIR)/cpt

cpt-resume: ## Resume CPT from last checkpoint
	$(PYTHON) $(TRAINING)/train_cpt.py \
		--model_name $(MODEL) \
		--data_path $(DATA_DIR)/cpt_train.jsonl \
		--output_dir $(CKPT_DIR)/cpt \
		--resume_from $$(ls -td $(CKPT_DIR)/cpt/checkpoint-* 2>/dev/null | head -1)

# ─── Stage 2: Supervised Fine-Tuning ───────────────────────────────────────

sft: ## Stage 2: SFT on instruction data (ChatML)
	$(PYTHON) $(TRAINING)/train_sft.py \
		--base_model $(CKPT_DIR)/cpt/final \
		--data_path $(DATA_DIR)/sft_train.jsonl \
		--output_dir $(CKPT_DIR)/sft

sft-resume: ## Resume SFT from last checkpoint
	$(PYTHON) $(TRAINING)/train_sft.py \
		--base_model $(CKPT_DIR)/cpt/final \
		--data_path $(DATA_DIR)/sft_train.jsonl \
		--output_dir $(CKPT_DIR)/sft \
		--resume_from $$(ls -td $(CKPT_DIR)/sft/checkpoint-* 2>/dev/null | head -1)

# ─── Stage 3: DPO Alignment ────────────────────────────────────────────────

dpo: prepare-dpo ## Stage 3: DPO alignment using preference pairs
	$(PYTHON) $(TRAINING)/train_dpo.py \
		--base_model $(CKPT_DIR)/sft/final \
		--chosen_path $(DATA_DIR)/dpo_chosen.jsonl \
		--rejected_path $(DATA_DIR)/dpo_rejected.jsonl \
		--output_dir $(CKPT_DIR)/dpo

# ─── Evaluation ─────────────────────────────────────────────────────────────

eval: ## Evaluate final (DPO) model
	$(PYTHON) $(TRAINING)/eval.py \
		--model_path $(CKPT_DIR)/dpo/final \
		--output_dir $(CKPT_DIR)/eval

eval-baseline: ## Evaluate unmodified base model
	$(PYTHON) $(TRAINING)/eval.py \
		--model_path $(MODEL) \
		--baseline \
		--output_dir $(CKPT_DIR)/eval-baseline

eval-sft: ## Evaluate after SFT (before DPO)
	$(PYTHON) $(TRAINING)/eval.py \
		--model_path $(CKPT_DIR)/sft/final \
		--output_dir $(CKPT_DIR)/eval-sft

eval-compare: ## Compare eval results across stages
	@echo "=== Baseline ===" && cat $(CKPT_DIR)/eval-baseline/eval_results.json 2>/dev/null | $(PYTHON) -m json.tool | head -20 || echo "(not found)"
	@echo "\n=== SFT ===" && cat $(CKPT_DIR)/eval-sft/eval_results.json 2>/dev/null | $(PYTHON) -m json.tool | head -20 || echo "(not found)"
	@echo "\n=== Final (DPO) ===" && cat $(CKPT_DIR)/eval/eval_results.json 2>/dev/null | $(PYTHON) -m json.tool | head -20 || echo "(not found)"

# ─── Export ─────────────────────────────────────────────────────────────────

export-gguf: ## Export to GGUF Q4_K_M (for Ollama/llama.cpp)
	$(PYTHON) -c "from unsloth import FastLanguageModel; \
		model, tok = FastLanguageModel.from_pretrained('$(CKPT_DIR)/dpo/final', max_seq_length=32768, load_in_4bit=True); \
		model.save_pretrained_gguf('$(CKPT_DIR)/gguf', tok, quantization_method='q4_k_m')"

export-merged: ## Merge LoRA into full 16-bit model
	$(PYTHON) -c "from unsloth import FastLanguageModel; \
		model, tok = FastLanguageModel.from_pretrained('$(CKPT_DIR)/dpo/final', max_seq_length=32768, load_in_4bit=False); \
		model.save_pretrained_merged('$(CKPT_DIR)/merged', tok, save_method='merged_16bit')"

push-hf: ## Push merged model to HuggingFace Hub
	$(PYTHON) -c "from unsloth import FastLanguageModel; \
		model, tok = FastLanguageModel.from_pretrained('$(CKPT_DIR)/dpo/final', max_seq_length=32768, load_in_4bit=True); \
		model.push_to_hub_merged('slm-solana', tok, save_method='merged_16bit')"

# ─── Training utilities ────────────────────────────────────────────────────

gpu-check: ## Verify GPU availability
	nvidia-smi
	$(PYTHON) -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')"

disk-check: ## Check disk usage
	df -h /workspace 2>/dev/null || df -h .
	du -sh $(CKPT_DIR)/* 2>/dev/null || echo "No checkpoints yet"
	du -sh $(DATA_DIR)/* 2>/dev/null || echo "No data yet"

clean-checkpoints: ## Remove intermediate checkpoints (keep final models)
	find $(CKPT_DIR) -name "checkpoint-*" -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Intermediate checkpoints cleaned"

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'
