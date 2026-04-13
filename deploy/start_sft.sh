#!/bin/bash
# Start SFT training on Akash/cloud instance.
# Usage:
#   Phase 1 (validation): bash start_sft.sh phase1
#   Phase 2 (full):       bash start_sft.sh phase2
#   Resume:               bash start_sft.sh resume /workspace/checkpoints/sft/checkpoint-500

export PATH=/opt/conda/bin:$PATH
export HF_HOME=/workspace/cache/huggingface
export TRANSFORMERS_CACHE=/workspace/cache/huggingface
export PYTHONUNBUFFERED=1
export TORCHINDUCTOR_DISABLE=1
export UNSLOTH_COMPILE_DISABLE=1
export TORCH_COMPILE_DISABLE=1

PHASE="${1:-phase1}"
RESUME_FROM="${2:-}"

case "$PHASE" in
  phase1)
    echo "=== Phase 1: Validation run (10K records, 1 epoch) ==="
    nohup python3 -u /workspace/scripts/train_sft.py \
      --data-path /workspace/data/sft_10k.jsonl \
      --num-train-epochs 1 \
      --learning-rate 2e-5 \
      --eval-steps 50 \
      --save-steps 100 \
      > /workspace/logs/sft_phase1.log 2>&1 &
    echo "PID: $! | Log: /workspace/logs/sft_phase1.log"
    ;;
  phase2)
    echo "=== Phase 2: Full training (50K records, 3 epochs) ==="
    nohup python3 -u /workspace/scripts/train_sft.py \
      --data-path /workspace/data/sft_50k.jsonl \
      --num-train-epochs 3 \
      --learning-rate 1e-5 \
      --eval-steps 200 \
      --save-steps 500 \
      --warmup-ratio 0.1 \
      > /workspace/logs/sft_phase2.log 2>&1 &
    echo "PID: $! | Log: /workspace/logs/sft_phase2.log"
    ;;
  resume)
    echo "=== Resuming from checkpoint: $RESUME_FROM ==="
    nohup python3 -u /workspace/scripts/train_sft.py \
      --data-path /workspace/data/sft_50k.jsonl \
      --resume-from "$RESUME_FROM" \
      > /workspace/logs/sft_resume.log 2>&1 &
    echo "PID: $! | Log: /workspace/logs/sft_resume.log"
    ;;
  *)
    echo "Usage: bash start_sft.sh [phase1|phase2|resume] [checkpoint_path]"
    ;;
esac
