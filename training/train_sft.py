#!/usr/bin/env python3
"""Stage 2: Supervised Fine-Tuning (SFT) on instruction data.

Takes the CPT checkpoint and fine-tunes on instruction-following data
(Q&A pairs, code generation, Solana-specific tasks) in ChatML format.

Usage:
    python training/train_sft.py
    python training/train_sft.py --base-model /workspace/checkpoints/cpt/final
    python training/train_sft.py --resume-from /workspace/checkpoints/sft/checkpoint-1000
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import torch
from datasets import load_dataset
from transformers import HfArgumentParser, TrainerCallback
from trl import SFTTrainer, SFTConfig
from unsloth import FastLanguageModel


@dataclass
class ModelConfig:
    # Use CPT checkpoint as base, or original model for SFT-only
    base_model: str = field(default="/workspace/checkpoints/cpt/final")
    max_seq_length: int = field(default=32768)
    load_in_4bit: bool = field(default=True)
    dtype: str = field(default="auto")

@dataclass
class DataConfig:
    data_path: str = field(default="/workspace/data/sft_train.jsonl")
    val_split: float = field(default=0.05)
    max_samples: int = field(default=0)

@dataclass
class SFTRunConfig:
    output_dir: str = field(default="/workspace/checkpoints/sft")
    num_train_epochs: int = field(default=3)
    per_device_train_batch_size: int = field(default=1)
    gradient_accumulation_steps: int = field(default=4)
    learning_rate: float = field(default=1e-5)
    lr_scheduler_type: str = field(default="cosine")
    warmup_ratio: float = field(default=0.1)
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
    # LoRA — use same or compatible config as CPT
    lora_r: int = field(default=64)
    lora_alpha: int = field(default=128)
    lora_dropout: float = field(default=0.0)
    # W&B
    report_to: str = field(default="wandb")
    run_name: str = field(default="slm-sft")


# System prompt for Solana assistant
SYSTEM_PROMPT = (
    "You are SLM, an expert Solana and Anchor development assistant. "
    "Provide accurate, secure, and up-to-date code using modern Anchor 0.30+ patterns "
    "(solana-foundation/anchor, InitSpace, ctx.bumps.field_name). "
    "When uncertain, say so rather than guessing. "
    "Never suggest reentrancy guards (Solana prevents reentrancy via CPI depth limits). "
    "Never reference coral-xyz/anchor or declare_id! — these are deprecated."
)


def format_chatml(example):
    """Format a record into ChatML for SFT training."""
    messages = example.get("messages")
    if messages:
        # Already in ChatML format
        return {"text": format_messages_to_text(messages)}

    # Fall back to content field (Q&A format)
    content = example.get("text", example.get("content", ""))
    if "### Question" in content and "### Answer" in content:
        parts = content.split("### Answer")
        question = parts[0].replace("### Question\n", "").strip()
        answer = parts[1].strip() if len(parts) > 1 else ""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ]
        return {"text": format_messages_to_text(messages)}

    # Plain text — wrap as assistant response
    return {"text": content}


def format_messages_to_text(messages: list[dict]) -> str:
    """Convert messages list to ChatML text format."""
    parts = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
    # Add generation prompt
    parts.append("<|im_start|>assistant\n")
    return "\n".join(parts)


class EvalLogCallback(TrainerCallback):
    def on_evaluate(self, args, state, control, metrics=None, **kwargs):
        if metrics:
            step = state.global_step
            loss = metrics.get("eval_loss", 0)
            print(f"  [Step {step}] eval_loss={loss:.4f}")


def main():
    parser = HfArgumentParser((ModelConfig, DataConfig, SFTRunConfig))
    model_cfg, data_cfg, train_cfg = parser.parse_args_into_dataclasses()

    print("=" * 60)
    print("  SLM — Supervised Fine-Tuning (SFT)")
    print("=" * 60)
    print(f"  Base:      {model_cfg.base_model}")
    print(f"  Data:      {data_cfg.data_path}")
    print(f"  Output:    {train_cfg.output_dir}")
    print(f"  Epochs:    {train_cfg.num_train_epochs}")
    print(f"  LR:        {train_cfg.learning_rate}")
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

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"  Trainable: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

    # ── 3. Load and format dataset ──
    print(f"[3/4] Loading SFT dataset from {data_cfg.data_path}...")
    dataset = load_dataset("json", data_files=data_cfg.data_path, split="train")

    if data_cfg.max_samples > 0:
        dataset = dataset.select(range(min(data_cfg.max_samples, len(dataset))))

    # Format to ChatML
    dataset = dataset.map(format_chatml, remove_columns=dataset.column_names)

    split = dataset.train_test_split(test_size=data_cfg.val_split, seed=train_cfg.seed)
    train_dataset = split["train"]
    eval_dataset = split["test"]
    print(f"  Train: {len(train_dataset):,}  Val: {len(eval_dataset):,}")

    # Print a sample
    print(f"\n  Sample (first 300 chars):")
    print(f"  {train_dataset[0]['text'][:300]}...")

    # ── 4. Training ──
    print("\n[4/4] Starting SFT training...")

    training_args = SFTConfig(
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
        max_seq_length=model_cfg.max_seq_length,
        dataset_text_field="text",
        packing=False,  # Don't pack for instruction tuning
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        args=training_args,
        callbacks=[EvalLogCallback()],
    )

    resume_path = train_cfg.resume_from if train_cfg.resume_from else None
    trainer.train(resume_from_checkpoint=resume_path)

    # ── Save ──
    final_path = Path(train_cfg.output_dir) / "final"
    print(f"\nSaving model to {final_path}...")
    trainer.save_model(str(final_path))
    tokenizer.save_pretrained(str(final_path))

    print("\n✓ SFT training complete!")
    print(f"  Model saved to: {final_path}")
    print(f"  Next step: Run DPO with training/train_dpo.py")


if __name__ == "__main__":
    main()
