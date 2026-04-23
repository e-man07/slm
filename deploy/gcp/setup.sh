#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID=$(gcloud config get-value project)
ZONE="us-east1-b"
REGION="us-east1"
VM_NAME="sealevel-api"
MACHINE_TYPE="e2-small"

echo "==> Project: $PROJECT_ID"
echo "==> Zone: $ZONE"

# 1. Reserve a static IP
echo "==> Reserving static IP..."
gcloud compute addresses create sealevel-ip --region="$REGION" 2>/dev/null || true
STATIC_IP=$(gcloud compute addresses describe sealevel-ip --region="$REGION" --format="get(address)")
echo "    Static IP: $STATIC_IP"

# 2. Create firewall rules
echo "==> Creating firewall rules..."
gcloud compute firewall-rules create allow-http \
  --allow=tcp:80 --target-tags=http-server \
  --description="Allow HTTP" 2>/dev/null || true
gcloud compute firewall-rules create allow-https \
  --allow=tcp:443 --target-tags=https-server \
  --description="Allow HTTPS" 2>/dev/null || true

# 3. Create VM with Container-Optimized OS
echo "==> Creating VM..."
gcloud compute instances create "$VM_NAME" \
  --zone="$ZONE" \
  --machine-type="$MACHINE_TYPE" \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --tags=http-server,https-server \
  --address="$STATIC_IP" \
  --boot-disk-size=20GB

echo "==> Waiting for VM to be ready..."
sleep 30

# 4. Install Docker + Docker Compose on the VM
echo "==> Installing Docker on VM..."
gcloud compute ssh "$VM_NAME" --zone="$ZONE" --command='
  sudo apt-get update -qq
  sudo apt-get install -y -qq ca-certificates curl gnupg
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt-get update -qq
  sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
  sudo usermod -aG docker $USER
'

# 5. Copy deployment files to VM
echo "==> Copying deployment files..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

gcloud compute scp --zone="$ZONE" --recurse \
  "$SCRIPT_DIR/docker-compose.yml" \
  "$SCRIPT_DIR/Caddyfile" \
  "$VM_NAME":~/deploy/

gcloud compute scp --zone="$ZONE" --recurse \
  "$REPO_ROOT/slm-mcp/" \
  "$VM_NAME":~/slm-mcp/

# 6. Print next steps
echo ""
echo "============================================"
echo "  VM created: $VM_NAME"
echo "  Static IP:  $STATIC_IP"
echo "============================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Point DNS A records to $STATIC_IP:"
echo "   api.sealevel.tech → $STATIC_IP"
echo "   mcp.sealevel.tech → $STATIC_IP"
echo ""
echo "2. SSH into the VM and create .env:"
echo "   gcloud compute ssh $VM_NAME --zone=$ZONE"
echo "   cd ~/deploy"
echo "   cp .env.example .env  # then fill in Akash URLs"
echo ""
echo "3. Start services:"
echo "   docker compose up -d --build"
echo ""
echo "4. Verify:"
echo "   curl https://api.sealevel.tech/health"
echo "   curl https://mcp.sealevel.tech/health"
