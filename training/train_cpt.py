#!/usr/bin/env python3
"""Stage 1: Continued Pre-Training (CPT) on Solana corpus.

Trains Qwen3-Coder-30B-A3B on the full Solana corpus (code, docs, Q&A)
using causal language modeling. This teaches the model Solana domain knowledge.

Usage:
    python training/train_cpt.py
    python training/train_cpt.py --data /path/to/cpt_train.jsonl
    python training/train_cpt.py --resume-from /path/to/checkpoint
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import torch
from datasets import load_dataset
from transformers import (
    HfArgumentParser,
    TrainerCallback,
)
from unsloth import FastLanguageModel, UnslothTrainer, UnslothTrainingArguments


# ── Configuration ──

@dataclass
class ModelConfig:
    model_name: str = field(default="Qwen/Qwen3-Coder-30B-A3B")
    max_seq_length: int = field(default=8192)
    load_in_4bit: bool = field(default=True)
    dtype: str = field(default="auto")  # auto, float16, bfloat16

@dataclass
class DataConfig:
    data_path: str = field(default="/workspace/data/cpt_train.jsonl")
    text_field: str = field(default="text")
    val_split: float = field(default=0.01)
    max_samples: int = field(default=0)  # 0 = use all

@dataclass
class CPTConfig:
    output_dir: str = field(default="/workspace/checkpoints/cpt")
    num_train_epochs: int = field(default=1)
    per_device_train_batch_size: int = field(default=1)
    gradient_accumulation_steps: int = field(default=8)
    learning_rate: float = field(default=2e-5)
    lr_scheduler_type: str = field(default="cosine")
    warmup_ratio: float = field(default=0.05)
    weight_decay: float = field(default=0.01)
    max_grad_norm: float = field(default=1.0)
    logging_steps: int = field(default=10)
    save_steps: int = field(default=500)
    eval_steps: int = field(default=500)
    save_total_limit: int = field(default=3)
    bf16: bool = field(default=True)
    gradient_checkpointing: bool = field(default=True)
    resume_from: str = field(default="")
    seed: int = field(default=42)
    # LoRA config
    lora_r: int = field(default=32)
    lora_alpha: int = field(default=64)
    lora_dropout: float = field(default=0.0)
    # W&B
    report_to: str = field(default="wandb")
    run_name: str = field(default="slm-cpt")


class EvalLogCallback(TrainerCallback):
    """Log eval metrics to console at each eval step."""
    def on_evaluate(self, args, state, control, metrics=None, **kwargs):
        if metrics:
            step = state.global_step
            loss = metrics.get("eval_loss", 0)
            ppl = metrics.get("eval_perplexity", 0)
            print(f"  [Step {step}] eval_loss={loss:.4f}  eval_ppl={ppl:.2f}")


def main():
    parser = HfArgumentParser((ModelConfig, DataConfig, CPTConfig))
    model_cfg, data_cfg, train_cfg = parser.parse_args_into_dataclasses()

    print("=" * 60)
    print("  SLM — Continued Pre-Training (CPT)")
    print("=" * 60)
    print(f"  Model:     {model_cfg.model_name}")
    print(f"  Data:      {data_cfg.data_path}")
    print(f"  Output:    {train_cfg.output_dir}")
    print(f"  LoRA r:    {train_cfg.lora_r}")
    print(f"  Seq len:   {model_cfg.max_seq_length}")
    print(f"  Batch:     {train_cfg.per_device_train_batch_size} × {train_cfg.gradient_accumulation_steps} grad_accum")
    print(f"  LR:        {train_cfg.learning_rate}")
    print(f"  Epochs:    {train_cfg.num_train_epochs}")
    print("=" * 60)

    # ── 1. Load model with Unsloth ──
    print("\n[1/5] Loading model with Unsloth...")
    dtype = None if model_cfg.dtype == "auto" else getattr(torch, model_cfg.dtype)

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_cfg.model_name,
        max_seq_length=model_cfg.max_seq_length,
        dtype=dtype,
        load_in_4bit=model_cfg.load_in_4bit,
    )

    # ── 2. Apply LoRA ──
    print("[2/5] Applying LoRA adapters...")
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

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"  Trainable: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

    # ── 3. Load dataset ──
    print(f"[3/5] Loading dataset from {data_cfg.data_path}...")
    dataset = load_dataset("json", data_files=data_cfg.data_path, split="train")

    if data_cfg.max_samples > 0:
        dataset = dataset.select(range(min(data_cfg.max_samples, len(dataset))))

    # Train/val split
    split = dataset.train_test_split(test_size=data_cfg.val_split, seed=train_cfg.seed)
    train_dataset = split["train"]
    eval_dataset = split["test"]
    print(f"  Train: {len(train_dataset):,}  Val: {len(eval_dataset):,}")

    # ── 4. Tokenize dataset ──
    print("[4/5] Tokenizing dataset...")
    eos_token = tokenizer.eos_token or ""

    def tokenize_fn(examples):
        texts = [t + eos_token for t in examples[data_cfg.text_field]]
        return tokenizer(
            texts,
            truncation=True,
            max_length=model_cfg.max_seq_length,
            padding=False,
        )

    train_dataset = train_dataset.map(
        tokenize_fn,
        batched=True,
        remove_columns=train_dataset.column_names,
        num_proc=4,
        desc="Tokenizing train",
    )
    eval_dataset = eval_dataset.map(
        tokenize_fn,
        batched=True,
        remove_columns=eval_dataset.column_names,
        num_proc=4,
        desc="Tokenizing eval",
    )
    print(f"  Tokenized train: {len(train_dataset):,}  eval: {len(eval_dataset):,}")

    # ── 5. Training ──
    print("[5/5] Starting training...")

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
        callbacks=[EvalLogCallback()],
    )

    # Resume from checkpoint if specified
    resume_path = train_cfg.resume_from if train_cfg.resume_from else None
    if resume_path:
        print(f"  Resuming from: {resume_path}")

    trainer.train(resume_from_checkpoint=resume_path)

    # ── Save ──
    final_path = Path(train_cfg.output_dir) / "final"
    print(f"\nSaving model to {final_path}...")
    trainer.save_model(str(final_path))
    tokenizer.save_pretrained(str(final_path))

    print("\n✓ CPT training complete!")
    print(f"  Model saved to: {final_path}")
    print(f"  Next step: Run SFT with training/train_sft.py")


if __name__ == "__main__":
    main()
