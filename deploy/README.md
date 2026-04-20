# Sealevel Deployment

Infrastructure for Sealevel inference stack and training jobs.

## Services

### `inference.sdl.yml` — Akash stack
4 services:
- **sglang** — model server (H100, Qwen2.5-Coder-7B-Instruct + LoRA)
- **litellm** — OpenAI-compatible proxy, rate-limiting master key auth
- **qdrant** — vector DB for RAG (persistent storage)
- **rag-api** — FastAPI service that fetches latest Solana docs, embeds into Qdrant, serves query endpoint

### `train.sdl.yml` — training container
A100 80GB with SSH + Jupyter Lab for manual CPT/SFT/DPO runs. See [`entrypoint.sh`](./entrypoint.sh).

### `rag-api/` — Docker image source
Python FastAPI + sentence-transformers. Image: `whyparabola/slm-rag-api:latest`.

## Deploy inference stack on Akash

### 1. Prepare

```bash
# Required env at deploy time (inject via Akash env or edit SDL):
#   HUGGING_FACE_HUB_TOKEN  — HF token (for model download)
#   LITELLM_MASTER_KEY      — random string, used by clients as Bearer token
#   SSH_PASSWORD            — strong password (fail-closed, no default)

# Generate secrets:
openssl rand -hex 32   # for LITELLM_MASTER_KEY
openssl rand -base64 24  # for SSH_PASSWORD
```

### 2. Deploy via Akash Console

Paste `inference.sdl.yml` into the Akash Console, fill placeholders (`<your-hf-token>`, `<your-litellm-master-key>`), accept a provider bid.

**Expected services after boot:**
- `sglang`: loads ~17 GB of model weights (first boot takes 8–12 min)
- `litellm`: starts once sglang exposes `/v1/models`
- `qdrant`: starts immediately
- `rag-api`: starts immediately, runs initial ingestion (~50 docs fetched from GitHub, takes ~2 min)

### 3. Verify

```bash
# LiteLLM ingress URL from Akash console
export SLM_URL=https://<ingress>.ingress.akash.pub
export KEY=<your-litellm-master-key>

# Test chat
curl $SLM_URL/v1/chat/completions \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"slm-solana","messages":[{"role":"user","content":"hello"}],"max_tokens":32}'

# RAG health
curl http://<provider>:<rag-port>/health

# RAG query
curl http://<provider>:<rag-port>/query \
  -X POST -H "Content-Type: application/json" \
  -d '{"query":"Anchor PDA","top_k":3}'
```

## Deploy training container

```bash
# Edit train.sdl.yml, set:
#   SSH_PASSWORD    — strong password
#   HUGGING_FACE_HUB_TOKEN  — HF token

# Deploy via Akash Console
# After boot, SSH in:
ssh -p <port> root@<provider>
cd /workspace
# Upload scripts/data via scp
# Kick off training:
bash /workspace/setup_env.sh
/workspace/venv/bin/python scripts/train_cpt.py
```

## Deploy MCP server

HTTP MCP server (`slm-mcp`) — see [`../slm-mcp/README.md`](../slm-mcp/README.md).

```bash
# GCP Cloud Run
gcloud run deploy slm-mcp \
  --image whyparabola/slm-mcp-server:latest \
  --region us-central1 --port 8080 --allow-unauthenticated \
  --set-env-vars MCP_TRANSPORT=http,SLM_API_URL=$SLM_URL,SLM_API_KEY=$KEY
```

## Observability

All services emit **structured JSON logs to stdout** — aggregate via Akash "View logs" or pipe to any log shipper (Vector, Fluent Bit, Grafana Loki, Datadog).

RAG API log format:

```json
{"ts":"2026-04-16T12:34:56Z","level":"INFO","logger":"rag-api","msg":"access","request_id":"abc123","method":"POST","path":"/query","status":200,"elapsed_ms":42}
```

Every request is tagged with `request_id` (also returned in `x-request-id` response header) for end-to-end tracing.

**Adding Prometheus metrics (later):**
Install `prometheus_client` in `rag-api/requirements.txt`, expose `/metrics` endpoint. SGLang has built-in Prometheus at `--enable-metrics` flag.

**Adding Sentry (later):**
Install `sentry-sdk[fastapi]`, set `SENTRY_DSN` env var, add `sentry_sdk.init(dsn=...)` at startup.

## HTTPS for inference services

Current state: LiteLLM ingress via Akash provides valid Let's Encrypt. SGLang / Qdrant / RAG API exposed over HTTP only.

**Production upgrade:** Add a Caddy sidecar to the SDL that fronts all services with HTTPS (auto-provisions Let's Encrypt certs). Example block:

```yaml
  caddy:
    image: caddy:2
    command:
      - /bin/sh
      - -c
      - |
        cat > /etc/caddy/Caddyfile <<EOF
        your-inference-domain.com {
          reverse_proxy /v1/* litellm:4000
          reverse_proxy /rag/* rag-api:8080
        }
        EOF
        caddy run --config /etc/caddy/Caddyfile
    expose:
      - port: 443
        as: 443
        to: [{ global: true }]
```

Point your domain at the Akash ingress and Caddy handles the rest.

## Qdrant backup

Qdrant persists to Akash volume but has no automated backup. **Daily snapshot script:**

```bash
# On your local machine or a cron-capable VM:
QDRANT_URL=http://provider.akash.pub:<port>
SNAPSHOT_NAME=$(date -u +%Y%m%dT%H%M%SZ).tar

# Trigger snapshot
curl -X POST "$QDRANT_URL/collections/solana-docs/snapshots"

# Download latest
curl "$QDRANT_URL/collections/solana-docs/snapshots/${SNAPSHOT_NAME}" -o "./backups/${SNAPSHOT_NAME}"

# Upload to S3 / GCS
aws s3 cp "./backups/${SNAPSHOT_NAME}" "s3://slm-backups/qdrant/"
```

**Restore:**

```bash
curl -X PUT "$QDRANT_URL/collections/solana-docs/snapshots/recover" \
  -H "Content-Type: application/json" \
  -d '{"location":"https://s3.amazonaws.com/slm-backups/qdrant/<snapshot>.tar"}'
```

Or re-run the initial ingestion: `POST /reingest` on the rag-api — takes ~2 min to rebuild from GitHub sources.

## Security checklist

- [ ] `LITELLM_MASTER_KEY` rotated from any previous deploy
- [ ] `SSH_PASSWORD` set to strong value (fails fast if unset)
- [ ] HF token scoped to read-only for base model + your LoRA repo
- [ ] Ingress URL is HTTPS (Akash provides valid Let's Encrypt cert)
- [ ] `.env.local` on all clients uses the new master key

## Troubleshooting

- **sglang `Not Acceptable: Client must accept both application/json and text/event-stream`** — client missing `Accept: application/json, text/event-stream` header
- **sglang `KeyError: 'gate_up_proj_moe'`** — SGLang `latest` changed LoRA handling for MoE. Pin to `v0.4.5.post2-cu124`.
- **LiteLLM `Got unexpected extra argument (bash)`** — Akash stripped the `command` override. Put everything in `args` with `bash -c "..."` pattern.
- **All services show "Ready 0/1"** — provider still pulling image; check "Events" tab for `ImagePullBackOff` vs normal pull delay.
