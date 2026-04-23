#!/usr/bin/env python3
"""Merge LoRA adapter into base model and push to HuggingFace."""

from unsloth import FastLanguageModel
from huggingface_hub import HfApi

CHECKPOINT = "/workspace/checkpoints/sft/final"
MERGED_DIR = "/workspace/checkpoints/merged"
REPO_ID = "WhyParabola/sealevel-solana-7b-merged"
TOKEN = "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"

print("Loading model + LoRA...")
model, tok = FastLanguageModel.from_pretrained(
    CHECKPOINT,
    max_seq_length=32768,
    load_in_4bit=False,
)

print("Saving merged 16-bit model...")
model.save_pretrained_merged(MERGED_DIR, tok, save_method="merged_16bit")
print(f"Merged model saved to {MERGED_DIR}")

print("Uploading to HuggingFace...")
api = HfApi(token=TOKEN)
api.create_repo(REPO_ID, exist_ok=True)
api.upload_folder(
    folder_path=MERGED_DIR,
    repo_id=REPO_ID,
    repo_type="model",
    commit_message="Sealevel v1: Qwen2.5-Coder-7B merged with LoRA",
    token=TOKEN,
)
print(f"Done! Pushed to: https://huggingface.co/{REPO_ID}")
