#!/usr/bin/env python3
"""Stage 2 v2: High-quality SFT with attention-only LoRA.

Designed for:
- Qwen3-Coder-8B-Instruct dense model (also works with MoE models via CLI override)
- Attention-only LoRA (compatible with sglang)
- Small dataset, high quality — higher rank, more epochs, careful scheduling
- Produces a LoRA adapter that can be:
  a) Merged into base model for serving
  b) Loaded directly by sglang with --enable-lora (if sglang supports it)
  c) Pushed to HuggingFace Hub

Usage:
    python train_sft_v2.py --data_path /workspace/data/sft_train.jsonl
    python train_sft_v2.py --data_path /workspace/data/sft_train.jsonl --push_to_hub
"""
from __future__ import annotations

import os
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import torch
from datasets import load_dataset
from transformers import HfArgumentParser, TrainerCallback
from unsloth import FastLanguageModel


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class ModelConfig:
    model_name: str = field(default="Qwen/Qwen3-Coder-8B-Instruct")
    max_seq_length: int = field(default=8192)
    load_in_4bit: bool = field(default=True)
    dtype: str = field(default="auto")


@dataclass
class DataConfig:
    data_path: str = field(default="/workspace/data/sft_train.jsonl")
    val_split: float = field(default=0.02)
    max_samples: int = field(default=0, metadata={"help": "0 = use all"})


@dataclass
class TrainConfig:
    output_dir: str = field(default="/workspace/checkpoints/sft-v2")
    num_train_epochs: int = field(default=5)
    per_device_train_batch_size: int = field(default=1)
    gradient_accumulation_steps: int = field(default=8)
    learning_rate: float = field(default=1e-4)
    lr_scheduler_type: str = field(default="cosine")
    warmup_ratio: float = field(default=0.05)
    weight_decay: float = field(default=0.01)
    max_grad_norm: float = field(default=1.0)
    logging_steps: int = field(default=5)
    save_steps: int = field(default=200)
    eval_steps: int = field(default=200)
    save_total_limit: int = field(default=3)
    bf16: bool = field(default=True)
    gradient_checkpointing: bool = field(default=True)
    resume_from: str = field(default="")
    seed: int = field(default=42)
    # LoRA — attention only, high rank for quality
    lora_r: int = field(default=64)
    lora_alpha: int = field(default=128)
    lora_dropout: float = field(default=0.05)
    # Existing adapter to continue training from
    existing_adapter: str = field(
        default="WhyParabola/slm-solana-lora",
        metadata={"help": "HF id or local path of existing LoRA adapter. Empty = train from scratch."},
    )
    # Hub
    push_to_hub: bool = field(default=False)
    hub_model_id: str = field(default="WhyParabola/slm-solana-lora-v2")
    # Reporting
    report_to: str = field(default="none")
    run_name: str = field(default="slm-sft-v2")


# ---------------------------------------------------------------------------
# System prompt (same as inference)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are Sealevel, an expert Solana and Anchor development assistant. "
    "Provide accurate, secure, and up-to-date code using modern Anchor 0.30+ patterns "
    "(solana-foundation/anchor, InitSpace, ctx.bumps.field_name). "
    "When uncertain, say so rather than guessing. "
    "Never suggest reentrancy guards (Solana prevents reentrancy via CPI depth limits). "
    "Never reference coral-xyz/anchor or declare_id! — these are deprecated."
)


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

class LogCallback(TrainerCallback):
    def __init__(self):
        self.start_time = time.time()

    def on_log(self, args, state, control, logs=None, **kwargs):
        if logs and "loss" in logs:
            elapsed = time.time() - self.start_time
            step = state.global_step
            total = state.max_steps
            eta = (elapsed / max(step, 1)) * (total - step)
            print(
                f"  Step {step:5d}/{total} | "
                f"loss={logs.get('loss', 0):.4f} | "
                f"lr={logs.get('learning_rate', 0):.2e} | "
                f"ETA={eta/3600:.1f}h"
            )

    def on_evaluate(self, args, state, control, metrics=None, **kwargs):
        if metrics:
            print(f"  EVAL | step={state.global_step} | eval_loss={metrics.get('eval_loss', '?'):.4f}")


# ---------------------------------------------------------------------------
# Data formatting
# ---------------------------------------------------------------------------

def format_chat(example, tokenizer):
    """Format a ChatML conversation for SFT."""
    messages = example.get("messages", [])

    # Ensure system prompt is present
    if not messages or messages[0].get("role") != "system":
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False,
    )
    return {"text": text}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = HfArgumentParser((ModelConfig, DataConfig, TrainConfig))
    model_cfg, data_cfg, train_cfg = parser.parse_args_into_dataclasses()

    print("=" * 60)
    print("  Sealevel — SFT v2 (Attention-Only LoRA)")
    print("=" * 60)
    print(f"  Model:     {model_cfg.model_name}")
    print(f"  Data:      {data_cfg.data_path}")
    print(f"  Output:    {train_cfg.output_dir}")
    print(f"  LoRA:      r={train_cfg.lora_r}, alpha={train_cfg.lora_alpha}")
    print(f"  Target:    q_proj, k_proj, v_proj, o_proj (attention only)")
    print(f"  Epochs:    {train_cfg.num_train_epochs}")
    print(f"  LR:        {train_cfg.learning_rate}")
    print(f"  Batch:     {train_cfg.per_device_train_batch_size} × {train_cfg.gradient_accumulation_steps}")
    print("=" * 60)

    # ── 1. Load model ──
    print("\n[1/5] Loading model...")
    dtype = None if model_cfg.dtype == "auto" else getattr(torch, model_cfg.dtype)
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_cfg.model_name,
        max_seq_length=model_cfg.max_seq_length,
        dtype=dtype,
        load_in_4bit=model_cfg.load_in_4bit,
    )

    # ── 2. Load existing LoRA adapter, then continue training ──
    existing_adapter = train_cfg.existing_adapter
    if existing_adapter:
        print(f"[2/5] Loading existing LoRA adapter: {existing_adapter}")
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, existing_adapter, is_trainable=True)
        # Enable gradient checkpointing
        if train_cfg.gradient_checkpointing:
            model.enable_input_require_grads()
            model.gradient_checkpointing_enable()
    else:
        print("[2/5] Applying fresh attention-only LoRA...")
        model = FastLanguageModel.get_peft_model(
            model,
            r=train_cfg.lora_r,
            lora_alpha=train_cfg.lora_alpha,
            lora_dropout=train_cfg.lora_dropout,
            target_modules=[
                "q_proj", "k_proj", "v_proj", "o_proj",
            ],
            target_parameters=[],  # Skip MoE expert layers
            bias="none",
            use_gradient_checkpointing="unsloth",
            random_state=train_cfg.seed,
        )

    # Print trainable params
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"  Trainable: {trainable:,} / {total:,} ({trainable/total:.2%})")

    # ── 3. Load dataset ──
    print(f"[3/5] Loading dataset from {data_cfg.data_path}...")
    dataset = load_dataset("json", data_files=data_cfg.data_path, split="train")

    if data_cfg.max_samples > 0:
        dataset = dataset.select(range(min(data_cfg.max_samples, len(dataset))))

    # Format into ChatML
    dataset = dataset.map(
        lambda x: format_chat(x, tokenizer),
        remove_columns=dataset.column_names,
        num_proc=4,
        desc="Formatting",
    )

    # Split
    split = dataset.train_test_split(test_size=data_cfg.val_split, seed=train_cfg.seed)
    train_dataset = split["train"]
    eval_dataset = split["test"]
    print(f"  Train: {len(train_dataset):,}  Val: {len(eval_dataset):,}")

    # ── 4. Tokenize ──
    print("[4/5] Tokenizing...")
    eos_token = tokenizer.eos_token

    def tokenize_fn(examples):
        texts = [t + eos_token for t in examples["text"]]
        return tokenizer(
            texts,
            truncation=True,
            max_length=model_cfg.max_seq_length,
            padding=False,
        )

    train_dataset = train_dataset.map(
        tokenize_fn, batched=True,
        remove_columns=train_dataset.column_names,
        num_proc=4, desc="Tokenizing train",
    )
    eval_dataset = eval_dataset.map(
        tokenize_fn, batched=True,
        remove_columns=eval_dataset.column_names,
        num_proc=4, desc="Tokenizing eval",
    )

    # ── 5. Train ──
    print("[5/5] Starting training...")
    from unsloth import UnslothTrainer, UnslothTrainingArguments

    training_args = UnslothTrainingArguments(
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
        eval_strategy="steps",
        eval_steps=train_cfg.eval_steps,
        save_total_limit=train_cfg.save_total_limit,
        bf16=train_cfg.bf16,
        gradient_checkpointing=train_cfg.gradient_checkpointing,
        report_to=train_cfg.report_to,
        run_name=train_cfg.run_name,
        seed=train_cfg.seed,
    )

    trainer = UnslothTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        args=training_args,
        callbacks=[LogCallback()],
    )

    # Resume if checkpoint exists
    resume_path = None
    if train_cfg.resume_from:
        resume_path = train_cfg.resume_from
    else:
        # Auto-detect latest checkpoint
        ckpt_dir = Path(train_cfg.output_dir)
        if ckpt_dir.exists():
            ckpts = sorted(ckpt_dir.glob("checkpoint-*"), key=lambda p: int(p.name.split("-")[1]))
            if ckpts:
                resume_path = str(ckpts[-1])
                print(f"  Resuming from {resume_path}")

    trainer.train(resume_from_checkpoint=resume_path)

    # ── Save final ──
    print("\nSaving final model...")
    final_dir = str(Path(train_cfg.output_dir) / "final")
    model.save_pretrained(final_dir)
    tokenizer.save_pretrained(final_dir)
    print(f"  Saved to {final_dir}")

    # ── Push to Hub ──
    if train_cfg.push_to_hub:
        print(f"\nPushing to HuggingFace Hub: {train_cfg.hub_model_id}")
        model.push_to_hub(train_cfg.hub_model_id, tokenizer=tokenizer, save_method="lora")
        print("  Pushed!")

    # ── Merge and save (for sglang serving) ──
    print("\nMerging LoRA into base model...")
    merged_dir = str(Path(train_cfg.output_dir) / "merged")
    model.save_pretrained_merged(merged_dir, tokenizer, save_method="merged_16bit")
    print(f"  Merged model saved to {merged_dir}")

    print("\nDone! Next steps:")
    print(f"  1. Copy merged model to inference container")
    print(f"  2. Or push LoRA to HF: --push_to_hub --hub_model_id your-id/slm-solana-lora-v2")
    print(f"  3. Run eval: python training/eval.py --model_path {final_dir}")


if __name__ == "__main__":
    main()
