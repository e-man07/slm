#!/usr/bin/env python3
"""Stage 3: Direct Preference Optimization (DPO) for alignment.

Takes the SFT checkpoint and aligns the model using preference pairs
from the Asymmetric Research misinformation report. Teaches the model
to prefer correct Solana patterns over deprecated/wrong ones.

Usage:
    python training/train_dpo.py
    python training/train_dpo.py --base-model /workspace/checkpoints/sft/final
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import torch
from datasets import Dataset
from transformers import HfArgumentParser, TrainerCallback
from trl import DPOTrainer, DPOConfig
from unsloth import FastLanguageModel, PatchDPOTrainer

# Patch DPO for Unsloth efficiency
PatchDPOTrainer()


@dataclass
class ModelConfig:
    base_model: str = field(default="/workspace/checkpoints/sft/final")
    max_seq_length: int = field(default=4096)  # Shorter for DPO pairs
    load_in_4bit: bool = field(default=True)
    dtype: str = field(default="auto")

@dataclass
class DataConfig:
    chosen_path: str = field(default="/workspace/data/dpo_chosen.jsonl")
    rejected_path: str = field(default="/workspace/data/dpo_rejected.jsonl")

@dataclass
class DPORunConfig:
    output_dir: str = field(default="/workspace/checkpoints/dpo")
    num_train_epochs: int = field(default=2)
    per_device_train_batch_size: int = field(default=1)
    gradient_accumulation_steps: int = field(default=4)
    learning_rate: float = field(default=5e-6)
    lr_scheduler_type: str = field(default="cosine")
    warmup_ratio: float = field(default=0.1)
    weight_decay: float = field(default=0.01)
    max_grad_norm: float = field(default=1.0)
    logging_steps: int = field(default=1)
    save_steps: int = field(default=50)
    save_total_limit: int = field(default=2)
    bf16: bool = field(default=True)
    gradient_checkpointing: bool = field(default=True)
    seed: int = field(default=42)
    # DPO specific
    beta: float = field(default=0.1)  # KL penalty coefficient
    max_prompt_length: int = field(default=1024)
    max_length: int = field(default=4096)
    # LoRA
    lora_r: int = field(default=32)  # Smaller for DPO
    lora_alpha: int = field(default=64)
    lora_dropout: float = field(default=0.0)
    # W&B
    report_to: str = field(default="wandb")
    run_name: str = field(default="slm-dpo")


SYSTEM_PROMPT = (
    "You are SLM, an expert Solana and Anchor development assistant. "
    "Provide accurate, secure, and up-to-date code using modern Anchor 0.30+ patterns."
)


def load_dpo_dataset(chosen_path: str, rejected_path: str) -> Dataset:
    """Load DPO preference pairs from chosen/rejected JSONL files.

    Expected format: Each record has a 'content' or 'messages' field.
    Chosen and rejected files are aligned by index (same prompts).
    """
    chosen_records = []
    with open(chosen_path) as f:
        for line in f:
            if line.strip():
                chosen_records.append(json.loads(line))

    rejected_records = []
    with open(rejected_path) as f:
        for line in f:
            if line.strip():
                rejected_records.append(json.loads(line))

    # Pair them up
    pairs = min(len(chosen_records), len(rejected_records))
    print(f"  Loaded {pairs} preference pairs")

    prompts = []
    chosen_responses = []
    rejected_responses = []

    for i in range(pairs):
        c = chosen_records[i]
        r = rejected_records[i]

        # Extract from messages format
        c_messages = c.get("messages") or c.get("content", "")
        r_messages = r.get("messages") or r.get("content", "")

        if isinstance(c_messages, list):
            # ChatML format: extract prompt and response
            prompt_parts = []
            c_response = ""
            for msg in c_messages:
                if msg["role"] == "assistant":
                    c_response = msg["content"]
                else:
                    prompt_parts.append(f"<|im_start|>{msg['role']}\n{msg['content']}<|im_end|>")
            prompt = "\n".join(prompt_parts)
        elif isinstance(c_messages, str) and "### Question" in c_messages:
            parts = c_messages.split("### Answer")
            prompt = f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n<|im_start|>user\n{parts[0].replace('### Question', '').strip()}<|im_end|>"
            c_response = parts[1].strip() if len(parts) > 1 else ""
        else:
            prompt = f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n<|im_start|>user\nExplain this Solana concept.<|im_end|>"
            c_response = str(c_messages)

        # Extract rejected response
        if isinstance(r_messages, list):
            r_response = ""
            for msg in r_messages:
                if msg["role"] == "assistant":
                    r_response = msg["content"]
        elif isinstance(r_messages, str) and "### Answer" in r_messages:
            parts = r_messages.split("### Answer")
            r_response = parts[1].strip() if len(parts) > 1 else ""
        else:
            r_response = str(r_messages)

        prompts.append(prompt)
        chosen_responses.append(c_response)
        rejected_responses.append(r_response)

    return Dataset.from_dict({
        "prompt": prompts,
        "chosen": chosen_responses,
        "rejected": rejected_responses,
    })


def main():
    parser = HfArgumentParser((ModelConfig, DataConfig, DPORunConfig))
    model_cfg, data_cfg, train_cfg = parser.parse_args_into_dataclasses()

    print("=" * 60)
    print("  SLM — Direct Preference Optimization (DPO)")
    print("=" * 60)
    print(f"  Base:    {model_cfg.base_model}")
    print(f"  Chosen:  {data_cfg.chosen_path}")
    print(f"  Rejected:{data_cfg.rejected_path}")
    print(f"  Beta:    {train_cfg.beta}")
    print(f"  LR:      {train_cfg.learning_rate}")
    print("=" * 60)

    # ── 1. Load model ──
    print("\n[1/4] Loading model...")
    dtype = None if model_cfg.dtype == "auto" else getattr(torch, model_cfg.dtype)

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_cfg.base_model,
        max_seq_length=model_cfg.max_seq_length,
        dtype=dtype,
        load_in_4bit=model_cfg.load_in_4bit,
    )

    # ── 2. Apply LoRA ──
    print("[2/4] Applying LoRA adapters...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=train_cfg.lora_r,
        lora_alpha=train_cfg.lora_alpha,
        lora_dropout=train_cfg.lora_dropout,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=train_cfg.seed,
    )

    # ── 3. Load DPO dataset ──
    print(f"[3/4] Loading DPO preference pairs...")
    dpo_dataset = load_dpo_dataset(data_cfg.chosen_path, data_cfg.rejected_path)

    # Print sample
    print(f"\n  Sample pair:")
    print(f"  Prompt:   {dpo_dataset[0]['prompt'][:150]}...")
    print(f"  Chosen:   {dpo_dataset[0]['chosen'][:150]}...")
    print(f"  Rejected: {dpo_dataset[0]['rejected'][:150]}...")

    # ── 4. Training ──
    print("\n[4/4] Starting DPO training...")

    training_args = DPOConfig(
        output_dir=train_cfg.output_dir,
        num_train_epochs=train_cfg.num_train_epochs,
        per_device_train_batch_size=train_cfg.per_device_train_batch_size,
        gradient_accumulation_steps=train_cfg.gradient_accumulation_steps,
        learning_rate=train_cfg.learning_rate,
        lr_scheduler_type=train_cfg.lr_scheduler_type,
        warmup_ratio=train_cfg.warmup_ratio,
        weight_decay=train_cfg.weight_decay,
        max_grad_norm=train_cfg.max_grad_norm,
        logging_steps=train_cfg.logging_steps,
        save_steps=train_cfg.save_steps,
        save_total_limit=train_cfg.save_total_limit,
        bf16=train_cfg.bf16,
        gradient_checkpointing=train_cfg.gradient_checkpointing,
        report_to=train_cfg.report_to,
        run_name=train_cfg.run_name,
        seed=train_cfg.seed,
        beta=train_cfg.beta,
        max_prompt_length=train_cfg.max_prompt_length,
        max_length=train_cfg.max_length,
    )

    trainer = DPOTrainer(
        model=model,
        ref_model=None,  # Unsloth handles reference model efficiently
        tokenizer=tokenizer,
        train_dataset=dpo_dataset,
        args=training_args,
    )

    trainer.train()

    # ── Save ──
    final_path = Path(train_cfg.output_dir) / "final"
    print(f"\nSaving model to {final_path}...")
    trainer.save_model(str(final_path))
    tokenizer.save_pretrained(str(final_path))

    print("\n✓ DPO alignment complete!")
    print(f"  Model saved to: {final_path}")
    print(f"  Next step: Run evaluation with training/eval.py")


if __name__ == "__main__":
    main()
