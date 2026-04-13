#!/usr/bin/env python3
"""SFT training for SLM — optimized for MoE + progressive validation.

Usage:
    # Phase 1: Quick validation (10K records, 1 epoch)
    python train_sft.py --max-samples 10000 --num-train-epochs 1 --eval-steps 50 --save-steps 100

    # Phase 2: Full training (50-100K records, 3 epochs)
    python train_sft.py --max-samples 50000 --num-train-epochs 3

    # Resume from checkpoint
    python train_sft.py --resume-from /workspace/checkpoints/sft/checkpoint-1000
"""
from __future__ import annotations

# Disable torch.compile/dynamo before any other imports — prevents flex_attention crash
import torch._dynamo
torch._dynamo.config.disable = True

import os
from dataclasses import dataclass, field
from pathlib import Path

import torch
from datasets import load_dataset
from transformers import HfArgumentParser, TrainerCallback

# Use FastModel for MoE models (Triton grouped-GEMM kernels = 6-12x faster)
try:
    from unsloth import FastModel
    USE_FAST_MODEL = True
    print("Using FastModel (MoE optimized)")
except ImportError:
    from unsloth import FastLanguageModel as FastModel
    USE_FAST_MODEL = False
    print("WARNING: FastModel not available, using FastLanguageModel (slower for MoE)")

from trl import SFTTrainer, SFTConfig


# -- Config --

@dataclass
class ModelConfig:
    base_model: str = field(default="Qwen/Qwen3-Coder-30B-A3B-Instruct")
    max_seq_length: int = field(default=4096)  # 4K is enough for most SFT pairs, doubles throughput
    load_in_4bit: bool = field(default=True)
    dtype: str = field(default="auto")

@dataclass
class DataConfig:
    data_path: str = field(default="/workspace/data/sft_train.jsonl")
    val_split: float = field(default=0.02)
    max_samples: int = field(default=0)  # 0 = use all; 10000 for Phase 1, 50000 for Phase 2

@dataclass
class SFTRunConfig:
    output_dir: str = field(default="/workspace/checkpoints/sft")
    num_train_epochs: int = field(default=3)
    per_device_train_batch_size: int = field(default=2)  # 2 fits with seq_len 4096 on A100
    gradient_accumulation_steps: int = field(default=4)  # effective batch = 8
    learning_rate: float = field(default=2e-5)  # higher for Phase 1, use 1e-5 for Phase 2
    lr_scheduler_type: str = field(default="cosine")
    warmup_ratio: float = field(default=0.05)
    weight_decay: float = field(default=0.01)
    max_grad_norm: float = field(default=1.0)
    logging_steps: int = field(default=5)
    save_steps: int = field(default=500)
    eval_steps: int = field(default=200)
    save_total_limit: int = field(default=3)
    bf16: bool = field(default=True)
    gradient_checkpointing: bool = field(default=True)
    resume_from: str = field(default="")
    seed: int = field(default=42)
    lora_r: int = field(default=16)  # 16 is faster, minimal quality loss vs 32
    lora_alpha: int = field(default=32)
    lora_dropout: float = field(default=0.0)
    report_to: str = field(default="none")
    run_name: str = field(default="slm-sft")


SYSTEM_PROMPT = (
    "You are SLM, an expert Solana and Anchor development assistant. "
    "Provide accurate, secure, and up-to-date code using modern Anchor 0.30+ patterns "
    "(solana-foundation/anchor, InitSpace, ctx.bumps.field_name). "
    "When uncertain, say so rather than guessing. "
    "Never suggest reentrancy guards (Solana prevents reentrancy via CPI depth limits). "
    "Never reference coral-xyz/anchor or declare_id! - these are deprecated."
)

# Test prompts for qualitative evaluation during training
QUALITY_CHECK_PROMPTS = [
    "Write an Anchor instruction that initializes a PDA counter account.",
    "How do I transfer SPL tokens using Anchor 0.30+?",
    "What is wrong with using declare_id! in modern Anchor?",
]


def format_chatml(example):
    """Format a record into ChatML text for SFT training."""
    messages = example.get("messages")
    if messages:
        parts = []
        for msg in messages:
            parts.append(f"<|im_start|>{msg['role']}\n{msg['content']}<|im_end|>")
        return {"text": "\n".join(parts)}

    content = example.get("text", example.get("content", ""))
    if "### Question" in content and "### Answer" in content:
        parts = content.split("### Answer")
        question = parts[0].replace("### Question\n", "").strip()
        answer = parts[1].strip() if len(parts) > 1 else ""
        text = (
            f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n"
            f"<|im_start|>user\n{question}<|im_end|>\n"
            f"<|im_start|>assistant\n{answer}<|im_end|>"
        )
        return {"text": text}

    return {"text": content}


class EvalLogCallback(TrainerCallback):
    """Log eval metrics clearly."""
    def on_evaluate(self, args, state, control, metrics=None, **kwargs):
        if metrics:
            step = state.global_step
            eval_loss = metrics.get("eval_loss", 0)
            train_loss = state.log_history[-2].get("loss", 0) if len(state.log_history) >= 2 else 0
            gap = eval_loss - train_loss
            print(f"\n  [Step {step}] eval_loss={eval_loss:.4f}  train_loss={train_loss:.4f}  gap={gap:.4f}")
            if gap > 0.5:
                print(f"  WARNING: Large train/eval gap ({gap:.2f}) - possible overfitting!")


class QualityCheckCallback(TrainerCallback):
    """Run qualitative checks on Solana prompts every N steps.

    Uses on_evaluate (which receives the model) instead of on_log (which does not).
    Disables gradient checkpointing temporarily for generation compatibility.
    """
    def __init__(self, tokenizer, model_ref=None, check_every=200):
        self.tokenizer = tokenizer
        self.model_ref = model_ref  # Store model reference since not all hooks pass it
        self.check_every = check_every

    def on_evaluate(self, args, state, control, model=None, **kwargs):
        if state.global_step == 0 or state.global_step % self.check_every != 0:
            return

        actual_model = model or self.model_ref
        if actual_model is None:
            return

        print(f"\n{'='*60}")
        print(f"  QUALITATIVE CHECK (step {state.global_step})")
        print(f"{'='*60}")

        actual_model.eval()
        # Temporarily disable gradient checkpointing for generation
        if hasattr(actual_model, "gradient_checkpointing_disable"):
            actual_model.gradient_checkpointing_disable()

        for prompt in QUALITY_CHECK_PROMPTS:
            text = (
                f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n"
                f"<|im_start|>user\n{prompt}<|im_end|>\n"
                f"<|im_start|>assistant\n"
            )
            inputs = self.tokenizer(text, return_tensors="pt").to(actual_model.device)
            try:
                with torch.no_grad():
                    outputs = actual_model.generate(
                        **inputs,
                        max_new_tokens=200,
                        temperature=0.0,
                        do_sample=False,
                        use_cache=False,  # Must be False with gradient checkpointing
                    )
                response = self.tokenizer.decode(
                    outputs[0][inputs["input_ids"].shape[1]:],
                    skip_special_tokens=True,
                )
                print(f"\n  Q: {prompt}")
                print(f"  A: {response[:300]}...")
            except Exception as e:
                print(f"\n  Q: {prompt}")
                print(f"  A: [Generation failed: {e}]")

        # Re-enable gradient checkpointing for training
        if hasattr(actual_model, "gradient_checkpointing_enable"):
            actual_model.gradient_checkpointing_enable()
        actual_model.train()
        print(f"{'='*60}\n")


def main():
    parser = HfArgumentParser((ModelConfig, DataConfig, SFTRunConfig))
    model_cfg, data_cfg, train_cfg = parser.parse_args_into_dataclasses()

    print("=" * 60)
    print("  SLM - Supervised Fine-Tuning (SFT)")
    print("=" * 60)
    print(f"  Base:      {model_cfg.base_model}")
    print(f"  Data:      {data_cfg.data_path}")
    print(f"  Samples:   {data_cfg.max_samples or 'all'}")
    print(f"  Output:    {train_cfg.output_dir}")
    print(f"  Epochs:    {train_cfg.num_train_epochs}")
    print(f"  LR:        {train_cfg.learning_rate}")
    print(f"  LoRA r:    {train_cfg.lora_r}")
    print(f"  Seq len:   {model_cfg.max_seq_length}")
    print(f"  Batch:     {train_cfg.per_device_train_batch_size} x {train_cfg.gradient_accumulation_steps} = {train_cfg.per_device_train_batch_size * train_cfg.gradient_accumulation_steps}")
    print(f"  Packing:   True")
    print("=" * 60)

    # -- 1. Load model --
    print("\n[1/4] Loading model...")
    dtype = None if model_cfg.dtype == "auto" else getattr(torch, model_cfg.dtype)

    model, tokenizer = FastModel.from_pretrained(
        model_name=model_cfg.base_model,
        max_seq_length=model_cfg.max_seq_length,
        dtype=dtype,
        load_in_4bit=model_cfg.load_in_4bit,
    )

    # -- 2. Apply LoRA --
    print("[2/4] Applying LoRA adapters...")
    lora_kwargs = dict(
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
    # target_parameters=[] disables MoE expert LoRA (128 experts = too slow/OOM)
    try:
        model = FastModel.get_peft_model(model, target_parameters=[], **lora_kwargs)
    except TypeError:
        # Older Unsloth versions don't support target_parameters
        model = FastModel.get_peft_model(model, **lora_kwargs)

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"  Trainable: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

    # -- 3. Load and format dataset --
    print(f"[3/4] Loading SFT dataset...")
    dataset = load_dataset("json", data_files=data_cfg.data_path, split="train")

    if data_cfg.max_samples > 0:
        dataset = dataset.shuffle(seed=train_cfg.seed).select(
            range(min(data_cfg.max_samples, len(dataset)))
        )
        print(f"  Selected {len(dataset):,} samples (shuffled)")

    dataset = dataset.map(format_chatml, remove_columns=dataset.column_names)

    split = dataset.train_test_split(test_size=data_cfg.val_split, seed=train_cfg.seed)
    train_dataset = split["train"]
    eval_dataset = split["test"]
    print(f"  Train: {len(train_dataset):,}  Val: {len(eval_dataset):,}")
    print(f"  Sample: {train_dataset[0]['text'][:200]}...")

    # -- 4. Training --
    print("\n[4/4] Starting SFT training...")

    # Fix Unsloth overriding eos_token to non-vocab '<EOS_TOKEN>'
    if tokenizer.eos_token not in tokenizer.get_vocab():
        tokenizer.eos_token = "<|im_end|>"
        print(f"  Fixed eos_token to: {tokenizer.eos_token}")

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
        max_length=model_cfg.max_seq_length,
        dataset_text_field="text",
        packing=True,  # 2-3x speedup from eliminating padding
    )

    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        args=training_args,
        callbacks=[
            EvalLogCallback(),
            QualityCheckCallback(tokenizer, model_ref=model, check_every=200),
        ],
    )

    # Calculate expected timeline
    total_steps = len(train_dataset) * train_cfg.num_train_epochs // (
        train_cfg.per_device_train_batch_size * train_cfg.gradient_accumulation_steps
    )
    print(f"\n  Estimated total steps: ~{total_steps:,}")
    print(f"  First checkpoint at step {train_cfg.save_steps}")
    print(f"  First eval at step {train_cfg.eval_steps}")
    print(f"  First quality check at step 200")

    resume_path = train_cfg.resume_from if train_cfg.resume_from else None
    if resume_path:
        print(f"  Resuming from: {resume_path}")

    trainer.train(resume_from_checkpoint=resume_path)

    # -- Save --
    final_path = Path(train_cfg.output_dir) / "final"
    print(f"\nSaving model to {final_path}...")
    trainer.save_model(str(final_path))
    tokenizer.save_pretrained(str(final_path))

    print("\nSFT training complete!")
    print(f"  Model saved to: {final_path}")
    print(f"  Next: Run eval with training/eval.py")
    print(f"  Then: Run DPO with training/train_dpo.py")


if __name__ == "__main__":
    main()
