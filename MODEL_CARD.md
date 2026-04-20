---
license: agpl-3.0
base_model: Qwen/Qwen3-Coder-8B-Instruct
tags:
  - solana
  - anchor
  - rust
  - code-generation
  - lora
  - peft
language:
  - en
library_name: peft
pipeline_tag: text-generation
---

# Sealevel — Solana Language Model (LoRA adapter)

A LoRA fine-tune of [Qwen3-Coder-8B-Instruct](https://huggingface.co/Qwen/Qwen3-Coder-8B-Instruct) specialized for Solana and Anchor development.

HuggingFace: [`WhyParabola/slm-solana-lora`](https://huggingface.co/WhyParabola/slm-solana-lora)

## Model Details

| | |
|---|---|
| **Base model** | Qwen3-Coder-8B-Instruct (8B dense, all params active per token) |
| **Adapter type** | LoRA (QLoRA 4-bit during training) |
| **LoRA rank** | 32 |
| **LoRA alpha** | 64 |
| **Target modules** | `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj` |
| **Trainable params** | ~400M (~5% of base) |
| **Training framework** | Unsloth + TRL + PEFT |
| **Quantization** | nf4 (QLoRA 4-bit base + fp16 LoRA for training), bf16 for serving |
| **Adapter size** | 51 MB |
| **Context** | 32K tokens (serving), 128K native |

## Intended Use

Solana + Anchor smart-contract development assistance:
- Write Anchor programs (counter, escrow, staking, AMM, NFT, DAO, etc.)
- Modern Anchor 0.30+ patterns (`declare_program!`, `InitSpace`, `ctx.bumps.field_name`)
- CPI patterns, PDA derivation, error handling
- SPL Token + Token-2022 operations
- Security review and migration from deprecated patterns
- Transaction lifecycle explanations

**Not intended for:** general-purpose coding (use base model or GPT-4), EVM/other chains, non-technical conversation.

## Training Data

731K SFT records from curated Solana ecosystem sources. See [`DATASET_CARD.md`](./data/DATASET_CARD.md) for full breakdown.

Key sources:
- Anchor framework source + examples (Apache-2.0)
- SPL Token program suite (Apache-2.0)
- Solana program-examples (Apache-2.0)
- Lumo Labs Solana datasets (AGPL-3.0) — **derivative models inherit AGPL-3.0**
- Synthetic Q&A pairs (14 generators, GLAN/Evol-Instruct/OSS-Instruct)
- Rust learning material (Apache-2.0)
- 397 DPO preference pairs (security + correctness)

**License note:** Because training data includes AGPL-3.0 content, this adapter and any model merging it must be distributed under AGPL-3.0 terms.

## Training Procedure

1. **Continued Pre-Training (CPT)** — 741K records, causal LM objective, 1 epoch
2. **Supervised Fine-Tuning (SFT)** — 731K ChatML records, 1 epoch, LR 2e-5, cosine schedule
3. **DPO** (planned, not yet run) — 397 chosen/rejected pairs for adversarial robustness

Hardware: 1× NVIDIA A100 80GB / H100 80GB (Akash Network).

## Evaluation

### Solana/Anchor benchmark (80 tasks, 7 categories)

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

### HumanEval (general coding sanity check)
**18/20 (90%)** — fine-tuning preserves general coding ability.

### Methodology
- Heuristic regex grading against pass/fail patterns (see [`training/eval.py`](./training/eval.py))
- Adversarial tasks check model refuses deprecated patterns (`declare_id!`, `coral-xyz/anchor`, `load_instruction_at`, reentrancy guards)
- Served via SGLang + LiteLLM + `logit_bias: {"18471": -30}` to suppress `declare_id!` token

## Limitations

1. **Adversarial robustness is 40%** — model sometimes engages with trick prompts (e.g., adding reentrancy guards when asked, despite guardrails). Mitigated via system prompt + logit bias; DPO training will improve this.
2. **Context window 32K** at current deployment (base supports 128K) — reduced to fit model + LoRA + KV cache on 80 GB VRAM. A10/L4 GPUs sufficient for inference; H100 used for best performance.
3. **Transaction category at 70%** — complex patterns (versioned tx, lookup tables, durable nonces) occasionally imperfect.
4. **Knowledge cutoff** — training data snapshot from March 2026; for newer Solana features (Alpenglow, latest SIMDs), the accompanying RAG pipeline provides up-to-date context.
5. **Does not self-verify code** — generated code should be reviewed and tested before deployment.

## Deployment

Served via SGLang on Akash Network (A10/L4 sufficient, H100 for best performance). Full stack:
- **SGLang** — model inference with LoRA merging
- **LiteLLM** — OpenAI-compatible proxy
- **Qdrant** — vector DB for retrieval
- **RAG API** — latest Solana docs injection

See [`deploy/README.md`](./deploy/README.md).

## How to Use

### OpenAI-compatible API

```bash
curl https://slm.dev/api/v1/chat/completions \
  -H "Authorization: Bearer slm_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "slm-solana",
    "messages": [{"role": "user", "content": "Write an Anchor counter program"}],
    "max_tokens": 1024
  }'
```

### Local inference (PEFT)

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen3-Coder-8B-Instruct", load_in_4bit=True)
model = PeftModel.from_pretrained(base, "WhyParabola/slm-solana-lora")
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3-Coder-8B-Instruct")

prompt = [
    {"role": "system", "content": "You are Sealevel, an expert Solana and Anchor developer. Use modern Anchor 0.30+ patterns."},
    {"role": "user", "content": "How do I derive a PDA in Anchor?"},
]
inputs = tokenizer.apply_chat_template(prompt, return_tensors="pt", add_generation_prompt=True).to(model.device)
output = model.generate(inputs, max_new_tokens=512, temperature=0.0)
print(tokenizer.decode(output[0][inputs.shape[1]:], skip_special_tokens=True))
```

## Ethical Considerations

- **Security-critical code**: this is a domain-specialized model, not an auditor. All generated Solana programs should be security-reviewed by a human before deployment to mainnet.
- **License propagation**: AGPL-3.0 copyleft applies. Self-hosting the model in a public service requires publishing source.
- **Adversarial prompts**: guardrails are imperfect; do not rely on model refusals for security-critical decisions.

## Citation

```bibtex
@software{slm2026,
  title  = {Sealevel — Solana Language Model},
  author = {Sealevel Contributors},
  year   = {2026},
  url    = {https://github.com/kshitij-hash/slm},
}
```

## Acknowledgments

- Qwen team (base model)
- Unsloth (fine-tuning framework)
- Solana Foundation (Sealevel RFP support)
- Akash Network (decentralized GPU compute)
- Lumo Labs (Solana datasets)
