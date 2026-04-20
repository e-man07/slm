#!/bin/bash
set -e
source /workspace/venv/bin/activate
cd /workspace

echo "=== Step 1: Evaluating SFT model ==="
python scripts/eval.py --model_path /workspace/checkpoints/sft/final --output_dir /workspace/results/sft-eval

echo "=== Step 2: Running DPO alignment ==="
python scripts/train_dpo.py --base_model /workspace/checkpoints/sft/final --chosen_path /workspace/data/dpo-chosen-adversarial.jsonl --rejected_path /workspace/data/dpo-rejected-adversarial.jsonl --output_dir /workspace/checkpoints/dpo

echo "=== Step 3: Evaluating DPO model ==="
python scripts/eval.py --model_path /workspace/checkpoints/dpo/final --output_dir /workspace/results/dpo-eval

echo "=== Step 4: Pushing to HuggingFace ==="
python -c "
from unsloth import FastLanguageModel
model, tok = FastLanguageModel.from_pretrained('/workspace/checkpoints/dpo/final', max_seq_length=32768, load_in_4bit=True)
model.push_to_hub_merged('WhyParabola/slm-solana-lora-v2', tok, save_method='lora')
"

echo "=== All done! ==="
