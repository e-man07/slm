"""Sealevel RAG API — Retrieval-Augmented Generation for Solana knowledge.

Embeds and indexes Solana docs, code, and research into Qdrant.
Serves context retrieval for the Sealevel inference pipeline.
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import sys
import textwrap
import time
import uuid
from contextvars import ContextVar
from typing import Optional

import httpx
import uvicorn

# GitHub auth for API rate limits (5000/hr vs 60/hr unauthenticated)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer


# ── Structured JSON logging ──
_request_id: ContextVar[str] = ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": _request_id.get(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(JsonFormatter())
_root = logging.getLogger()
_root.handlers = [_handler]
_root.setLevel(os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("rag-api")

# ── Config ──
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
COLLECTION = "solana-docs"
EMBEDDING_DIM = 384  # bge-small-en-v1.5
CHUNK_SIZE = 512  # tokens approx (chars / 4)
CHUNK_OVERLAP = 64
TOP_K = 5

app = FastAPI(title="Sealevel RAG API", version="1.0.0")
embedder: Optional[SentenceTransformer] = None
qdrant: Optional[QdrantClient] = None


@app.middleware("http")
async def request_id_and_access_log(request: Request, call_next):
    """Attach a request ID, log access, and propagate ID in response header."""
    req_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    token = _request_id.set(req_id)
    start = time.time()
    try:
        response = await call_next(request)
    except Exception as exc:
        elapsed_ms = int((time.time() - start) * 1000)
        log.exception("request failed")
        _request_id.reset(token)
        raise exc
    else:
        elapsed_ms = int((time.time() - start) * 1000)
        response.headers["x-request-id"] = req_id
        log.info(
            "access",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "elapsed_ms": elapsed_ms,
            },
        )
        _request_id.reset(token)
        return response


# ── Sources ──

DOCS_SOURCES = [
    # ── Solana official docs ──
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-docs/main/docs/intro/overview.md", "source": "solana-docs", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-docs/main/docs/intro/quick-start.md", "source": "solana-docs", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-docs/main/docs/core/accounts.md", "source": "solana-docs", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-docs/main/docs/core/transactions.md", "source": "solana-docs", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-docs/main/docs/core/programs.md", "source": "solana-docs", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-docs/main/docs/core/tokens.md", "source": "solana-docs", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-docs/main/docs/core/pda.md", "source": "solana-docs", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-docs/main/docs/core/cpi.md", "source": "solana-docs", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-docs/main/docs/core/fees.md", "source": "solana-docs", "type": "docs"},
    # Solana RPC / web3.js
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-docs/main/docs/rpc/http/index.md", "source": "solana-rpc", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-docs/main/docs/rpc/http/getAccountInfo.md", "source": "solana-rpc", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-docs/main/docs/rpc/http/getBalance.md", "source": "solana-rpc", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-docs/main/docs/rpc/http/getTransaction.md", "source": "solana-rpc", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-docs/main/docs/rpc/http/sendTransaction.md", "source": "solana-rpc", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-docs/main/docs/rpc/websocket/index.md", "source": "solana-rpc", "type": "docs"},
    # Solana advanced
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-docs/main/docs/advanced/lookup-tables.md", "source": "solana-docs", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-docs/main/docs/advanced/versions.md", "source": "solana-docs", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-docs/main/docs/advanced/retry.md", "source": "solana-docs", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-docs/main/docs/advanced/confirmation.md", "source": "solana-docs", "type": "docs"},

    # ── Anchor docs ──
    {"url": "https://raw.githubusercontent.com/coral-xyz/anchor/master/docs/src/getting-started/introduction.md", "source": "anchor-docs", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/coral-xyz/anchor/master/docs/src/getting-started/installation.md", "source": "anchor-docs", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/coral-xyz/anchor/master/docs/src/getting-started/basics.md", "source": "anchor-docs", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/coral-xyz/anchor/master/docs/src/references/account-types.md", "source": "anchor-docs", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/coral-xyz/anchor/master/docs/src/references/account-constraints.md", "source": "anchor-docs", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/coral-xyz/anchor/master/docs/src/references/space.md", "source": "anchor-docs", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/coral-xyz/anchor/master/CHANGELOG.md", "source": "anchor-changelog", "type": "docs"},

    # ── Solana cookbook ──
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-cookbook/master/docs/core-concepts/accounts.md", "source": "solana-cookbook", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-cookbook/master/docs/core-concepts/programs.md", "source": "solana-cookbook", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-cookbook/master/docs/core-concepts/transactions.md", "source": "solana-cookbook", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-cookbook/master/docs/core-concepts/pdas.md", "source": "solana-cookbook", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-cookbook/master/docs/core-concepts/cpi.md", "source": "solana-cookbook", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-cookbook/master/docs/references/token.md", "source": "solana-cookbook", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-cookbook/master/docs/references/nfts.md", "source": "solana-cookbook", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-cookbook/master/docs/references/accounts.md", "source": "solana-cookbook", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-cookbook/master/docs/references/programs.md", "source": "solana-cookbook", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-cookbook/master/docs/guides/serialization.md", "source": "solana-cookbook", "type": "docs"},

    # ── SPL docs ──
    {"url": "https://raw.githubusercontent.com/solana-labs/solana-program-library/master/token/program/README.md", "source": "spl-token", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-labs/solana-program-library/master/token/program-2022/README.md", "source": "spl-token-2022", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-labs/solana-program-library/master/associated-token-account/program/README.md", "source": "spl-ata", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-labs/solana-program-library/master/stake-pool/README.md", "source": "spl-stake-pool", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-labs/solana-program-library/master/governance/README.md", "source": "spl-governance", "type": "docs"},

    # ── Metaplex / NFT ──
    {"url": "https://raw.githubusercontent.com/metaplex-foundation/mpl-token-metadata/main/README.md", "source": "metaplex-metadata", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/metaplex-foundation/mpl-core/main/README.md", "source": "metaplex-core", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/metaplex-foundation/mpl-bubblegum/main/README.md", "source": "metaplex-bubblegum", "type": "docs"},

    # ── Solana whitepaper ──
    {"url": "https://solana.com/solana-whitepaper.pdf", "source": "solana-whitepaper", "type": "whitepaper"},
]

CODE_SOURCES = [
    # Anchor examples
    {"url": "https://api.github.com/repos/coral-xyz/anchor/contents/examples", "source": "anchor-examples", "type": "code", "lang": "rust"},
    # SPL token program
    {"url": "https://api.github.com/repos/solana-labs/solana-program-library/contents/token/program/src", "source": "spl-token", "type": "code", "lang": "rust"},
    # SPL token-2022 (Token Extensions)
    {"url": "https://api.github.com/repos/solana-labs/solana-program-library/contents/token/program-2022/src", "source": "spl-token-2022", "type": "code", "lang": "rust"},
    # Associated token account
    {"url": "https://api.github.com/repos/solana-labs/solana-program-library/contents/associated-token-account/program/src", "source": "spl-ata", "type": "code", "lang": "rust"},
    # Program examples — basics
    {"url": "https://api.github.com/repos/solana-developers/program-examples/contents/basics", "source": "program-examples", "type": "code", "lang": "rust"},
    # Program examples — tokens
    {"url": "https://api.github.com/repos/solana-developers/program-examples/contents/tokens", "source": "program-examples-tokens", "type": "code", "lang": "rust"},
    # Program examples — compression
    {"url": "https://api.github.com/repos/solana-developers/program-examples/contents/compression", "source": "program-examples-compression", "type": "code", "lang": "rust"},
    # Anchor framework lib source (core types)
    {"url": "https://api.github.com/repos/coral-xyz/anchor/contents/lang/src", "source": "anchor-lang-src", "type": "code", "lang": "rust"},
    # Anchor SPL crate
    {"url": "https://api.github.com/repos/coral-xyz/anchor/contents/spl/src", "source": "anchor-spl-src", "type": "code", "lang": "rust"},
    # Solana playground examples (TypeScript client code)
    {"url": "https://api.github.com/repos/solana-playground/solana-playground/contents/client/src/tutorials", "source": "solpg-tutorials", "type": "code", "lang": "ts"},

    # ── Production Anchor Programs (MIT/Apache-2.0) ──

    # Drift Protocol v2 — perpetuals DEX (Apache-2.0)
    {"url": "https://api.github.com/repos/drift-labs/protocol-v2/contents/programs/drift/src", "source": "drift-protocol", "type": "code", "lang": "rust"},

    # Raydium CLMM — concentrated liquidity AMM (Apache-2.0)
    {"url": "https://api.github.com/repos/raydium-io/raydium-clmm/contents/programs/amm/src", "source": "raydium-clmm", "type": "code", "lang": "rust"},

    # Raydium CP-Swap — constant product with Token-2022 (Apache-2.0)
    {"url": "https://api.github.com/repos/raydium-io/raydium-cp-swap/contents/programs/cp-swap/src", "source": "raydium-cp-swap", "type": "code", "lang": "rust"},

    # OpenBook v2 — central limit order book (MIT)
    {"url": "https://api.github.com/repos/openbook-dex/openbook-v2/contents/programs/openbook-v2/src", "source": "openbook-v2", "type": "code", "lang": "rust"},

    # Anchor Escrow — canonical escrow pattern (MIT)
    {"url": "https://api.github.com/repos/ironaddicteddog/anchor-escrow/contents/programs/anchor-escrow/src", "source": "anchor-escrow", "type": "code", "lang": "rust"},

    # Saber StableSwap — Curve-style AMM (Apache-2.0)
    {"url": "https://api.github.com/repos/saber-hq/stable-swap/contents/stable-swap-program/program/src", "source": "saber-stableswap", "type": "code", "lang": "rust"},

    # Coral Multisig — multisig pattern (Apache-2.0)
    {"url": "https://api.github.com/repos/coral-xyz/multisig/contents/programs/multisig/src", "source": "coral-multisig", "type": "code", "lang": "rust"},

    # Helium — staking, oracles, DAOs (Apache-2.0)
    {"url": "https://api.github.com/repos/helium/helium-program-library/contents/programs/circuit-breaker/src", "source": "helium-circuit-breaker", "type": "code", "lang": "rust"},
    {"url": "https://api.github.com/repos/helium/helium-program-library/contents/programs/lazy-distributor/src", "source": "helium-lazy-distributor", "type": "code", "lang": "rust"},
    {"url": "https://api.github.com/repos/helium/helium-program-library/contents/programs/voter-stake-registry/src", "source": "helium-voter-stake", "type": "code", "lang": "rust"},

    # Jito StakeNet — validator staking (Apache-2.0)
    {"url": "https://api.github.com/repos/jito-foundation/stakenet/contents/programs/steward/src", "source": "jito-steward", "type": "code", "lang": "rust"},

    # Nosana — staking & rewards (MIT)
    {"url": "https://api.github.com/repos/nosana-ci/nosana-programs/contents/programs/nosana-staking/src", "source": "nosana-staking", "type": "code", "lang": "rust"},
    {"url": "https://api.github.com/repos/nosana-ci/nosana-programs/contents/programs/nosana-rewards/src", "source": "nosana-rewards", "type": "code", "lang": "rust"},
]

# Newer Solana tech — proposals, RFCs, blog content
BLOG_SOURCES = [
    # Alpenglow consensus
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-improvement-documents/main/proposals/0172-alpenglow.md", "source": "alpenglow-proposal", "type": "docs"},
    # Tower BFT
    {"url": "https://raw.githubusercontent.com/anza-xyz/agave/master/docs/src/proposals/tower-bft.md", "source": "tower-bft", "type": "docs"},
    # Firedancer
    {"url": "https://raw.githubusercontent.com/firedancer-io/firedancer/main/README.md", "source": "firedancer", "type": "docs"},
    # ZK Compression / Light Protocol
    {"url": "https://raw.githubusercontent.com/Lightprotocol/light-protocol/main/README.md", "source": "zk-compression", "type": "docs"},
    # Solana Actions / Blinks
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-docs/main/docs/advanced/actions.md", "source": "solana-actions", "type": "docs"},
    # SIMDs (Solana Improvement Documents)
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-improvement-documents/main/proposals/0047-syscall-precompile-verification.md", "source": "simd-0047", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/solana-foundation/solana-improvement-documents/main/proposals/0096-reward-full-priority-fee-to-validator.md", "source": "simd-0096", "type": "docs"},
    # Solana validator architecture
    {"url": "https://raw.githubusercontent.com/anza-xyz/agave/master/docs/src/validator/blockstore.md", "source": "agave-validator", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/anza-xyz/agave/master/docs/src/validator/tpu.md", "source": "agave-validator", "type": "docs"},
    {"url": "https://raw.githubusercontent.com/anza-xyz/agave/master/docs/src/validator/tvu.md", "source": "agave-validator", "type": "docs"},
    # Jito MEV
    {"url": "https://raw.githubusercontent.com/jito-foundation/jito-solana/master/README.md", "source": "jito-mev", "type": "docs"},
    # Marinade staking
    {"url": "https://raw.githubusercontent.com/marinade-finance/liquid-staking-program/main/README.md", "source": "marinade", "type": "docs"},
]


# ── Chunking ──

def chunk_text(text: str, source: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """Split text into overlapping chunks with metadata."""
    chunks = []
    # Approx chars per token
    char_size = chunk_size * 4
    char_overlap = overlap * 4

    # Clean up text
    text = re.sub(r'\n{3,}', '\n\n', text.strip())

    if len(text) < char_size:
        chunks.append({"text": text, "source": source, "chunk_idx": 0})
        return chunks

    start = 0
    idx = 0
    while start < len(text):
        end = start + char_size
        chunk = text[start:end]

        # Try to break at paragraph or sentence boundary
        if end < len(text):
            # Look for paragraph break
            para_break = chunk.rfind('\n\n')
            if para_break > char_size // 2:
                chunk = chunk[:para_break]
                end = start + para_break
            else:
                # Look for sentence break
                sent_break = max(chunk.rfind('. '), chunk.rfind('.\n'))
                if sent_break > char_size // 2:
                    chunk = chunk[:sent_break + 1]
                    end = start + sent_break + 1

        chunks.append({"text": chunk.strip(), "source": source, "chunk_idx": idx})
        start = end - char_overlap
        idx += 1

    return chunks


def chunk_code(code: str, source: str, filename: str = "") -> list[dict]:
    """Split code files into logical chunks (by function/struct boundaries)."""
    chunks = []
    # Split on function/struct/impl boundaries for Rust
    boundaries = re.split(r'(?=\n(?:pub )?(?:fn |struct |impl |mod |#\[program\]|#\[derive))', code)

    current = ""
    idx = 0
    for block in boundaries:
        if len(current) + len(block) > CHUNK_SIZE * 4:
            if current.strip():
                chunks.append({
                    "text": current.strip(),
                    "source": source,
                    "filename": filename,
                    "chunk_idx": idx,
                })
                idx += 1
            current = block
        else:
            current += block

    if current.strip():
        chunks.append({
            "text": current.strip(),
            "source": source,
            "filename": filename,
            "chunk_idx": idx,
        })

    return chunks


# ── Ingestion ──

async def fetch_url(url: str, retries: int = 3) -> Optional[str]:
    """Fetch content from URL with retry on rate limit."""
    headers = GITHUB_HEADERS if "github" in url else {}
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    return resp.text
                if resp.status_code in (403, 429):
                    wait = int(resp.headers.get("retry-after", 60 * (attempt + 1)))
                    log.warning(f"Rate limited on {url}, waiting {wait}s (attempt {attempt+1}/{retries})")
                    await asyncio.sleep(wait)
                    continue
                log.warning(f"Failed to fetch {url}: {resp.status_code}")
                return None
        except Exception as e:
            log.warning(f"Error fetching {url}: {e}")
            return None
    log.warning(f"Exhausted retries for {url}")
    return None


async def fetch_github_dir(api_url: str, source: str, lang: str = "rust") -> list[dict]:
    """Fetch code files using GitHub tree API (1 call per repo instead of per-directory)."""
    chunks = []
    exts = (".rs", ".ts", ".tsx") if lang == "ts" else (".rs",) if lang == "rust" else (".rs",)

    # Convert contents API URL to tree API URL for efficiency
    # e.g. api.github.com/repos/OWNER/REPO/contents/PATH -> api.github.com/repos/OWNER/REPO/git/trees/HEAD?recursive=1
    import re as _re
    m = _re.match(r'https://api\.github\.com/repos/([^/]+/[^/]+)/contents/(.*)', api_url)
    if not m:
        log.warning(f"Cannot parse GitHub URL: {api_url}")
        return chunks

    repo = m.group(1)
    subpath = m.group(2).rstrip('/')
    tree_url = f"https://api.github.com/repos/{repo}/git/trees/HEAD?recursive=1"

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            # One API call to get the entire file tree
            for attempt in range(3):
                resp = await client.get(tree_url, headers=GITHUB_HEADERS)
                if resp.status_code == 200:
                    break
                if resp.status_code in (403, 429):
                    wait = int(resp.headers.get("retry-after", 60 * (attempt + 1)))
                    log.warning(f"Rate limited on tree API for {repo}, waiting {wait}s")
                    await asyncio.sleep(wait)
                    continue
                log.warning(f"Tree API failed for {repo}: {resp.status_code}")
                return chunks
            else:
                log.warning(f"Exhausted retries for tree API {repo}")
                return chunks

            tree = resp.json().get("tree", [])

            # Filter files under subpath with matching extensions
            files = [
                item for item in tree
                if item["type"] == "blob"
                and item["path"].startswith(subpath + "/")
                and any(item["path"].endswith(ext) for ext in exts)
            ]

            # Limit to 50 files per source to avoid excessive downloads
            files = files[:50]
            log.info(f"  Found {len(files)} {lang} files under {repo}/{subpath}")

            # Download file contents via raw.githubusercontent.com (no API rate limit)
            default_branch = "main"
            # Try to detect branch from existing data
            for branch in ["main", "master"]:
                test_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{files[0]['path']}" if files else ""
                if test_url:
                    test_resp = await client.get(test_url, headers=GITHUB_HEADERS)
                    if test_resp.status_code == 200:
                        default_branch = branch
                        break

            for item in files:
                raw_url = f"https://raw.githubusercontent.com/{repo}/{default_branch}/{item['path']}"
                content = await fetch_url(raw_url)
                if content and len(content) > 100:
                    chunks.extend(chunk_code(content, source, item["path"]))

    except Exception as e:
        log.warning(f"Error fetching GitHub tree for {repo}: {e}")

    return chunks


async def ingest_all():
    """Fetch all sources, chunk, embed, and store in Qdrant."""
    global qdrant, embedder

    log.info("Starting ingestion...")
    all_chunks = []

    # Anchor patterns reference (bundled with the image)
    patterns_path = os.path.join(os.path.dirname(__file__), "anchor_patterns.md")
    if os.path.exists(patterns_path):
        content = open(patterns_path).read()
        chunks = chunk_text(content, "anchor-patterns-reference")
        all_chunks.extend(chunks)
        log.info(f"  -> {len(chunks)} chunks from anchor-patterns-reference (local)")

    # Docs sources
    for src in DOCS_SOURCES + BLOG_SOURCES:
        url = src["url"]
        if url.endswith(".pdf"):
            log.info(f"Skipping PDF (would need parser): {url}")
            continue
        log.info(f"Fetching {src['source']}: {url}")
        content = await fetch_url(url)
        if content:
            chunks = chunk_text(content, src["source"])
            all_chunks.extend(chunks)
            log.info(f"  -> {len(chunks)} chunks from {src['source']}")

    # Code sources
    for src in CODE_SOURCES:
        log.info(f"Fetching code: {src['source']}")
        chunks = await fetch_github_dir(src["url"], src["source"], src.get("lang", "rust"))
        all_chunks.extend(chunks)
        log.info(f"  -> {len(chunks)} chunks from {src['source']}")

    if not all_chunks:
        log.warning("No chunks to ingest!")
        return

    log.info(f"Total chunks: {len(all_chunks)}. Embedding...")

    # Embed all chunks
    texts = [c["text"] for c in all_chunks]
    embeddings = embedder.encode(texts, show_progress_bar=True, batch_size=32)

    # Upsert into Qdrant
    points = []
    for i, (chunk, emb) in enumerate(zip(all_chunks, embeddings)):
        point_id = hashlib.md5(chunk["text"][:200].encode()).hexdigest()
        points.append(PointStruct(
            id=int(point_id[:12], 16),  # Use first 12 hex chars as int ID
            vector=emb.tolist(),
            payload={
                "text": chunk["text"],
                "source": chunk.get("source", ""),
                "filename": chunk.get("filename", ""),
                "chunk_idx": chunk.get("chunk_idx", 0),
            },
        ))

    # Batch upsert
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        qdrant.upsert(collection_name=COLLECTION, points=batch)

    log.info(f"Ingested {len(points)} chunks into Qdrant collection '{COLLECTION}'")


# ── API ──

class QueryRequest(BaseModel):
    query: str
    top_k: int = TOP_K
    source_filter: Optional[str] = None


class QueryResult(BaseModel):
    text: str
    source: str
    score: float
    filename: str = ""


class QueryResponse(BaseModel):
    results: list[QueryResult]
    context: str  # Pre-formatted context string for injection into prompt


class IngestRequest(BaseModel):
    url: str
    source: str
    type: str = "docs"  # docs or code


class IngestTextRequest(BaseModel):
    text: str
    source: str
    type: str = "docs"


@app.on_event("startup")
async def startup():
    global embedder, qdrant

    log.info(f"Loading embedding model: {EMBEDDING_MODEL}")
    embedder = SentenceTransformer(EMBEDDING_MODEL)

    log.info(f"Connecting to Qdrant: {QDRANT_URL}")
    qdrant = QdrantClient(url=QDRANT_URL)

    # Create collection if not exists
    collections = [c.name for c in qdrant.get_collections().collections]
    if COLLECTION not in collections:
        qdrant.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )
        log.info(f"Created collection: {COLLECTION}")

        # Run initial ingestion
        await ingest_all()
    else:
        info = qdrant.get_collection(COLLECTION)
        log.info(f"Collection '{COLLECTION}' exists with {info.points_count} points")


@app.get("/health")
def health():
    count = 0
    if qdrant:
        try:
            info = qdrant.get_collection(COLLECTION)
            count = info.points_count
        except Exception:
            pass
    return {"status": "ok", "collection": COLLECTION, "points": count}


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """Retrieve relevant context for a query."""
    if not embedder or not qdrant:
        raise HTTPException(status_code=503, detail="Service not ready")

    # Embed query
    query_vec = embedder.encode(req.query).tolist()

    # Search Qdrant
    results = qdrant.search(
        collection_name=COLLECTION,
        query_vector=query_vec,
        limit=req.top_k,
    )

    items = []
    for r in results:
        items.append(QueryResult(
            text=r.payload.get("text", ""),
            source=r.payload.get("source", ""),
            score=r.score,
            filename=r.payload.get("filename", ""),
        ))

    # Format context for prompt injection
    context_parts = []
    for i, item in enumerate(items, 1):
        src = f"[{item.source}]"
        if item.filename:
            src += f" {item.filename}"
        context_parts.append(f"--- Reference {i} {src} (relevance: {item.score:.2f}) ---\n{item.text}")

    context = "\n\n".join(context_parts)

    return QueryResponse(results=items, context=context)


@app.post("/ingest_text")
async def ingest_text(req: IngestTextRequest):
    """Ingest raw text directly into the collection."""
    if not embedder or not qdrant:
        raise HTTPException(status_code=503, detail="Service not ready")

    if req.type == "code":
        chunks = chunk_code(req.text, req.source)
    else:
        chunks = chunk_text(req.text, req.source)

    if not chunks:
        raise HTTPException(status_code=400, detail="No chunks extracted")

    texts = [c["text"] for c in chunks]
    embeddings = embedder.encode(texts, batch_size=32)

    points = []
    for chunk, emb in zip(chunks, embeddings):
        point_id = hashlib.md5(chunk["text"][:200].encode()).hexdigest()
        points.append(PointStruct(
            id=int(point_id[:12], 16),
            vector=emb.tolist(),
            payload={
                "text": chunk["text"],
                "source": chunk.get("source", req.source),
                "filename": chunk.get("filename", ""),
                "chunk_idx": chunk.get("chunk_idx", 0),
            },
        ))

    qdrant.upsert(collection_name=COLLECTION, points=points)
    return {"status": "ok", "chunks_ingested": len(points), "source": req.source}


@app.post("/ingest")
async def ingest_url(req: IngestRequest):
    """Ingest a single URL into the collection."""
    if not embedder or not qdrant:
        raise HTTPException(status_code=503, detail="Service not ready")

    content = await fetch_url(req.url)
    if not content:
        raise HTTPException(status_code=400, detail=f"Failed to fetch {req.url}")

    if req.type == "code":
        chunks = chunk_code(content, req.source)
    else:
        chunks = chunk_text(content, req.source)

    if not chunks:
        raise HTTPException(status_code=400, detail="No chunks extracted")

    texts = [c["text"] for c in chunks]
    embeddings = embedder.encode(texts, batch_size=32)

    points = []
    for chunk, emb in zip(chunks, embeddings):
        point_id = hashlib.md5(chunk["text"][:200].encode()).hexdigest()
        points.append(PointStruct(
            id=int(point_id[:12], 16),
            vector=emb.tolist(),
            payload={
                "text": chunk["text"],
                "source": chunk.get("source", req.source),
                "filename": chunk.get("filename", ""),
                "chunk_idx": chunk.get("chunk_idx", 0),
            },
        ))

    qdrant.upsert(collection_name=COLLECTION, points=points)

    return {"status": "ok", "chunks_ingested": len(points), "source": req.source}


@app.post("/reingest")
async def reingest():
    """Re-run full ingestion (fetches latest docs from all sources)."""
    if not embedder or not qdrant:
        raise HTTPException(status_code=503, detail="Service not ready")

    # Drop and recreate collection
    qdrant.delete_collection(COLLECTION)
    qdrant.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )

    await ingest_all()

    info = qdrant.get_collection(COLLECTION)
    return {"status": "ok", "points": info.points_count}


# ── Inference Proxy with declare_id! cleanup ──────────────────────────────────

SGLANG_URL = os.environ.get("SGLANG_URL", "http://inference:30000/v1")

SYSTEM_PROMPT = (
    "You are Sealevel, an expert Solana and Anchor development assistant. "
    "Provide accurate, secure, and up-to-date code using modern Anchor 0.30+ "
    "patterns (solana-foundation/anchor, InitSpace, ctx.bumps.field_name). "
    "When uncertain, say so rather than guessing. Never suggest reentrancy "
    "guards (Solana prevents reentrancy via CPI depth limits). Never reference "
    "coral-xyz/anchor or declare_id! — these are deprecated."
)

DEPRECATED_PATTERNS = [
    # (pattern, replacement)
    ('declare_id!("', '#[program]\n// Program ID set in Anchor.toml\n// declare_program!("'),
    ("declare_id!(\"", '#[program]\n// Program ID set in Anchor.toml\n// declare_program!("'),
]

import re

def clean_response(text: str) -> str:
    """Remove declare_id! and other deprecated patterns from model output."""
    # Remove declare_id!("..."); lines in code
    text = re.sub(
        r'declare_id!\s*\(\s*"[A-Za-z0-9]+"\s*\)\s*;?\s*\n?',
        '// Program ID is set in Anchor.toml\n',
        text,
    )
    # Remove backtick-wrapped `declare_id!` mentions in text
    text = text.replace("`declare_id!`", "`declare_program!`")
    # Remove plain declare_id! mentions in text
    text = re.sub(r'declare_id!', 'declare_program!', text)
    # Replace coral-xyz/anchor with solana-foundation/anchor
    text = text.replace("coral-xyz/anchor", "solana-foundation/anchor")
    # Replace project-serum/anchor with solana-foundation/anchor
    text = text.replace("project-serum/anchor", "solana-foundation/anchor")
    # Replace ProgramResult with Result<()>
    text = text.replace("ProgramResult", "Result<()>")
    # Replace #[error] with #[error_code]
    text = re.sub(r'#\[error\]\s*\n', '#[error_code]\n', text)
    return text


class ChatRequest(BaseModel):
    model: str = "slm-solana"
    messages: list = []
    max_tokens: int = 4096
    temperature: float = 0.7
    stream: bool = False


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """Proxy to SGLang with system prompt injection and output cleanup."""
    body = await request.json()
    messages = body.get("messages", [])

    # Inject system prompt if missing
    if not messages or messages[0].get("role") != "system":
        messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})

    body["messages"] = messages

    # Forward to SGLang
    sglang_endpoint = f"{SGLANG_URL}/chat/completions"
    async with httpx.AsyncClient(timeout=120) as client:
        try:
            resp = await client.post(sglang_endpoint, json=body)
            data = resp.json()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"SGLang error: {e}")

    # Post-process: clean deprecated patterns
    if "choices" in data:
        for choice in data["choices"]:
            if "message" in choice and "content" in choice["message"]:
                choice["message"]["content"] = clean_response(
                    choice["message"]["content"]
                )

    return data


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
