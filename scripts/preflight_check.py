#!/usr/bin/env python3
"""Pre-flight check: verify everything is ready for training."""
import json, os, shutil, subprocess, datetime

print("=== 1. PYTHON PACKAGES ===")
packages = ["unsloth", "torch", "trl", "datasets", "transformers", "peft"]
for pkg in packages:
    try:
        mod = __import__(pkg)
        ver = getattr(mod, "__version__", "OK")
        print("  %s: %s" % (pkg, ver))
    except ImportError:
        print("  %s: MISSING !!!" % pkg)

print("\n=== 2. GPU ===")
import torch
print("  CUDA available: %s" % torch.cuda.is_available())
if torch.cuda.is_available():
    print("  GPU: %s" % torch.cuda.get_device_name(0))
    props = torch.cuda.get_device_properties(0)
    vram = getattr(props, "total_memory", getattr(props, "total_mem", 0))
    print("  VRAM: %.0f GB" % (vram / 1024**3))

print("\n=== 3. DATA FILES ===")
data_dir = "/workspace/data"
for fname in ["cpt_train.jsonl", "sft_train.jsonl", "dpo_chosen.jsonl", "dpo_rejected.jsonl"]:
    path = os.path.join(data_dir, fname)
    if os.path.exists(path):
        count = sum(1 for _ in open(path))
        size_mb = os.path.getsize(path) / 1024 / 1024
        print("  %s: %s records (%.0f MB)" % (fname, format(count, ","), size_mb))
    else:
        print("  %s: MISSING" % fname)

print("\n=== 4. TRAINING SCRIPTS ===")
scripts_dir = "/workspace/scripts"
for fname in ["train_cpt.py", "train_sft.py", "train_dpo.py", "eval.py"]:
    path = os.path.join(scripts_dir, fname)
    status = "OK" if os.path.exists(path) else "MISSING"
    print("  %s: %s" % (fname, status))

print("\n=== 5. TRAIN_CPT.PY CONFIG ===")
with open("/workspace/scripts/train_cpt.py") as f:
    content = f.read()
if 'report_to: str = field(default="none")' in content:
    print("  wandb: disabled (good)")
elif 'report_to: str = field(default="wandb")' in content:
    print("  wandb: ENABLED (will fail without key)")
else:
    print("  wandb: unknown config")
if "target_parameters" in content:
    print("  MoE fix (target_parameters): present")
else:
    print("  MoE fix (target_parameters): MISSING")

print("\n=== 6. DISK SPACE ===")
total, used, free = shutil.disk_usage("/workspace")
print("  Total: %.0f GB" % (total / 1024**3))
print("  Used: %.0f GB" % (used / 1024**3))
print("  Free: %.0f GB" % (free / 1024**3))

print("\n=== 7. MODEL CACHE ===")
cache_dir = "/workspace/cache/huggingface"
if os.path.exists(cache_dir):
    cache_size = sum(os.path.getsize(os.path.join(dp, f)) for dp, dn, fns in os.walk(cache_dir) for f in fns)
    print("  Cache size: %.1f GB" % (cache_size / 1024**3))
    found_qwen = False
    for root, dirs, files in os.walk(cache_dir):
        for d in dirs:
            if "qwen" in d.lower():
                print("  Found: %s" % d)
                found_qwen = True
                break
        if found_qwen:
            break
    if not found_qwen:
        print("  Qwen model: NOT CACHED (will download on first run ~20GB)")
else:
    print("  No cache directory")

print("\n=== 8. CONTAINER STABILITY ===")
result = subprocess.run(["ps", "-o", "lstart=", "-p", "1"], capture_output=True, text=True)
print("  PID 1 started: %s" % result.stdout.strip())
print("  Current time: %s" % datetime.datetime.now())

print("\n=== VERDICT ===")
