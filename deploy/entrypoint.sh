#!/bin/bash
# Minimal entrypoint - just install deps, start SSH, and stay alive.
# Run training manually via SSH.

mkdir -p /workspace/logs /workspace/cache/pip /run/sshd

# System deps
apt-get update -qq && apt-get install -y -qq openssh-server git wget >/dev/null 2>&1 || true
apt-get clean && rm -rf /var/lib/apt/lists/* 2>/dev/null || true

# SSH — fail closed if password not provided
if [ -z "$SSH_PASSWORD" ]; then
    echo "ERROR: SSH_PASSWORD env var must be set" >&2
    exit 1
fi
echo "root:${SSH_PASSWORD}" | chpasswd
sed -i 's/#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
sed -i 's/#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
/usr/sbin/sshd || true

# Pip
pip install -q --cache-dir=/workspace/cache/pip unsloth trl datasets wandb typer rich datasketch huggingface_hub jupyterlab 2>/dev/null || true

# Jupyter in background
nohup jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root --NotebookApp.token='' --NotebookApp.password='' --notebook-dir=/workspace >/workspace/logs/jupyter.log 2>&1 &

echo "=== Container ready. SSH in to start training. ==="

# Stay alive forever
while true; do sleep 86400; done
