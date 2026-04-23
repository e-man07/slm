import type { ReactNode } from "react"
import { CodeBlock } from "@/components/shared/code-block"

export interface DocTopic {
  slug: string
  label: string
  description: string
  section: string
  content: ReactNode
}

export const docTopics: DocTopic[] = [
  // ── Getting Started ──
  {
    slug: "quick-start",
    label: "Quick Start",
    section: "Getting Started",
    description: "Sign up and run your first Sealevel query in under 5 minutes.",
    content: (
      <>
        <section>
          <h2>1. Sign in</h2>
          <p>
            Go to <a href="/sign-in">slm.dev/sign-in</a> and sign in with GitHub or Google. Then
            generate an API key from the <a href="/dashboard">Dashboard</a>.
          </p>
        </section>
        <section>
          <h2>2. Pick a client</h2>
          <p>Sealevel ships four clients — use whichever fits your workflow:</p>
          <ul>
            <li>
              <a href="/docs/web">Web chat</a> — no install, fastest way to try it
            </li>
            <li>
              <a href="/docs/cli">CLI</a> — terminal chat, code generation, review, migration
            </li>
<li>
              <a href="/docs/mcp">MCP server</a> — Claude Code, Cursor, Windsurf integration
            </li>
          </ul>
        </section>
        <section>
          <h2>3. First query (curl)</h2>
          <CodeBlock
            language="bash"
            code={`curl https://api.sealevel.tech/v1/chat/completions \\
  -H "Authorization: Bearer slm_YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "sealevel",
    "messages": [{"role": "user", "content": "How do I derive a PDA in Anchor?"}],
    "max_tokens": 512
  }'`}
          />
        </section>
      </>
    ),
  },
  {
    slug: "authentication",
    label: "Authentication",
    section: "Getting Started",
    description: "OAuth sign-in, API keys, rate-limit tiers.",
    content: (
      <>
        <section>
          <h2>OAuth providers</h2>
          <p>Sign in with GitHub or Google at <a href="/sign-in">slm.dev/sign-in</a>. Then go to the <a href="/dashboard">Dashboard</a> and click <strong>Generate API Key</strong> to create your key.</p>
        </section>
        <section>
          <h2>API key format</h2>
          <p>
            Keys start with <code>slm_</code> followed by a 32-char hex token. Pass in the{" "}
            <code>Authorization</code> header:
          </p>
          <CodeBlock language="bash" code={`Authorization: Bearer slm_a1b2c3...`} />
        </section>
        <section>
          <h2>Rate-limit tiers</h2>
          <ul>
            <li><strong>Free</strong> (signed-in): 5 req/min, 100K tokens/day</li>
          </ul>
          <p>Limits reset at UTC midnight. Hit a limit and you get a 429 with <code>Retry-After</code>.</p>
        </section>
      </>
    ),
  },

  // ── Clients ──
  {
    slug: "web",
    label: "Web Chat",
    section: "Clients",
    description: "Use Sealevel directly at slm.dev/chat — no install needed.",
    content: (
      <>
        <section>
          <h2>What you get</h2>
          <ul>
            <li>Streaming chat with syntax-highlighted code blocks</li>
            <li>Chat history saved to your account (sign-in required)</li>
            <li>Transaction explainer at <a href="/explain/tx">/explain/tx</a></li>
            <li>Error decoder at <a href="/explain/error">/explain/error</a></li>
          </ul>
        </section>
        <section>
          <h2>Anonymous vs signed-in</h2>
          <p>Anonymous users get 3 req/min. Sign in for 5 req/min + chat history.</p>
        </section>
        <section>
          <h2>Stop generation</h2>
          <p>Click the Stop button while streaming — aborts the request mid-response.</p>
        </section>
      </>
    ),
  },
  {
    slug: "cli",
    label: "CLI",
    section: "Clients",
    description: "Install slm-cli and chat, generate Anchor programs, review code from your terminal.",
    content: (
      <>
        <section>
          <h2>Install</h2>
          <CodeBlock language="bash" code={`pip install slm-cli  # coming soon — install from source for now:
# git clone https://github.com/e-man07/slm && cd slm/slm-cli && pip install -e .`} />
          <p>
            Requires Python 3.10+. See the{" "}
            <a href="https://github.com/kshitij-hash/slm/tree/main/slm-cli" target="_blank" rel="noreferrer">
              source
            </a>{" "}
            for dev install.
          </p>
        </section>
        <section>
          <h2>Configure</h2>
          <CodeBlock
            language="bash"
            code={`slm config --api-key slm_YOUR_KEY
slm config --show`}
          />
          <p>
            API key is stored in the OS keyring (macOS Keychain, Windows Credential Locker, GNOME
            keyring/KWallet). Non-secret config lives in{" "}
            <code>~/.slm/config.toml</code>.
          </p>
        </section>
        <section>
          <h2>Commands</h2>
          <CodeBlock
            language="bash"
            code={`slm chat "How do I create a PDA?"        # one-shot
slm chat                                   # interactive REPL

slm gen "token vesting with linear unlock" -o src/lib.rs
slm review src/lib.rs
slm migrate src/lib.rs --write            # migrate in place
slm tests src/lib.rs > tests/program.ts

slm explain --tx 5U3...abc
slm explain --error 0x1771`}
          />
        </section>
        <section>
          <h2>Scripting</h2>
          <p>Use <code>--json</code> for machine-readable output:</p>
          <CodeBlock
            language="bash"
            code={`slm chat --json "explain Solana rent" | jq '.content'`}
          />
        </section>
        <section>
          <h2>Shell completion</h2>
          <CodeBlock
            language="bash"
            code={`slm --install-completion bash   # or zsh | fish`}
          />
        </section>
      </>
    ),
  },
  {
    slug: "mcp",
    label: "MCP Server",
    section: "Clients",
    description: "Use Sealevel from Claude Code, Cursor, Windsurf, or Codex via Model Context Protocol.",
    content: (
      <>
        <section>
          <h2>Prerequisites</h2>
          <p>
            You need a Sealevel API key. <a href="/sign-in">Sign in</a>, then generate one from the{" "}
            <a href="/dashboard">Dashboard</a>.
          </p>
        </section>
        <section>
          <h2>Add to Claude Code</h2>
          <CodeBlock
            language="bash"
            code={`claude mcp add --transport http sealevel https://mcp.sealevel.tech/mcp \\
  --header "Authorization: Bearer slm_YOUR_KEY"`}
          />
          <p>Replace <code>slm_YOUR_KEY</code> with your API key. Claude Code picks it up immediately.</p>
        </section>
        <section>
          <h2>Add to Cursor</h2>
          <p>Open Cursor Settings → MCP Servers, add:</p>
          <CodeBlock
            language="json"
            code={`{
  "mcpServers": {
    "sealevel": {
      "url": "https://mcp.sealevel.tech/mcp",
      "headers": {
        "Authorization": "Bearer slm_YOUR_KEY"
      }
    }
  }
}`}
          />
        </section>
        <section>
          <h2>Add to Windsurf</h2>
          <p>Open Windsurf Settings → MCP, add:</p>
          <CodeBlock
            language="json"
            code={`{
  "mcpServers": {
    "sealevel": {
      "url": "https://mcp.sealevel.tech/mcp",
      "headers": {
        "Authorization": "Bearer slm_YOUR_KEY"
      }
    }
  }
}`}
          />
        </section>
        <section>
          <h2>Add to OpenAI Codex</h2>
          <p>Add to your project&apos;s <code>.codex/config.json</code>:</p>
          <CodeBlock
            language="json"
            code={`{
  "mcpServers": {
    "sealevel": {
      "url": "https://mcp.sealevel.tech/mcp",
      "headers": {
        "Authorization": "Bearer slm_YOUR_KEY"
      }
    }
  }
}`}
          />
        </section>
        <section>
          <h2>Tools exposed</h2>
          <ul>
            <li><code>slm_chat</code> — ask a Solana/Anchor question</li>
            <li><code>slm_decode_error</code> — look up an error code</li>
            <li><code>slm_explain_tx</code> — explain a transaction by signature</li>
            <li><code>slm_migrate_code</code> — migrate old Anchor code to 0.30+</li>
            <li><code>slm_review_code</code> — security + deprecation review</li>
          </ul>
        </section>
        <section>
          <h2>Prompts + resources</h2>
          <p>Slash command in Claude Code:</p>
          <ul>
            <li><code>/mcp__slm__security-review</code> — security audit for Anchor code (checks signer validation, owner checks, overflow, PDA collisions, close constraints)</li>
          </ul>
          <p>Resources: <code>solana://errors</code> (complete error table), <code>solana://system-prompt</code> (Sealevel guardrails).</p>
        </section>
      </>
    ),
  },

  // ── API Reference ──
  {
    slug: "api-chat",
    label: "Chat Completions",
    section: "API Reference",
    description: "OpenAI-compatible /v1/chat/completions endpoint with SSE streaming.",
    content: (
      <>
        <section>
          <h2>Request</h2>
          <CodeBlock
            language="bash"
            code={`POST /v1/chat/completions
Authorization: Bearer slm_YOUR_KEY
Content-Type: application/json

{
  "model": "sealevel",
  "messages": [
    {"role": "system", "content": "You are Sealevel, an expert Solana developer..."},
    {"role": "user", "content": "Write an Anchor counter program"}
  ],
  "max_tokens": 1024,
  "temperature": 0.0,
  "stream": true,
  "stream_options": {"include_usage": true}
}`}
          />
        </section>
        <section>
          <h2>Streaming response</h2>
          <p>Server-sent events, each <code>data:</code> line is a JSON chunk:</p>
          <CodeBlock
            language="text"
            code={`data: {"choices":[{"delta":{"content":"Here"}}]}
data: {"choices":[{"delta":{"content":"'s"}}]}
...
data: {"usage":{"prompt_tokens":42,"completion_tokens":128,"total_tokens":170}}
data: [DONE]`}
          />
        </section>
        <section>
          <h2>Non-streaming</h2>
          <p>Omit <code>stream</code> or set <code>false</code>. Response follows the OpenAI schema with <code>choices[0].message.content</code>.</p>
        </section>
      </>
    ),
  },
  {
    slug: "api-explain",
    label: "Explain Endpoints",
    section: "API Reference",
    description: "Transaction explainer and error decoder.",
    content: (
      <>
        <section>
          <h2>Explain transaction</h2>
          <CodeBlock
            language="bash"
            code={`POST /api/explain/tx
Authorization: Bearer slm_YOUR_KEY
{"signature": "5U3...abc"}`}
          />
          <p>Returns a SSE stream: first a <code>tx_data</code> event with parsed Helius data, then LLM explanation deltas.</p>
        </section>
        <section>
          <h2>Decode error</h2>
          <CodeBlock
            language="bash"
            code={`POST /api/explain/error
{"error_code": "0x1771", "program_id": "optional"}`}
          />
          <p>Returns lookup result (name, message, program) plus streaming AI explanation.</p>
        </section>
      </>
    ),
  },
  {
    slug: "api-usage",
    label: "Usage Stats",
    section: "API Reference",
    description: "Per-key usage — today's count + 7-day history.",
    content: (
      <>
        <section>
          <h2>Request</h2>
          <CodeBlock
            language="bash"
            code={`GET /api/usage
Authorization: Bearer slm_YOUR_KEY`}
          />
        </section>
        <section>
          <h2>Response</h2>
          <CodeBlock
            language="json"
            code={`{
  "user": {"tier": "free"},
  "today": {"requests": 42, "tokens": 12345},
  "last_7_days": [
    {"date": "2026-04-16", "requests": 42, "tokens": 12345}
  ],
  "by_endpoint": [
    {"endpoint": "/api/chat", "requests": 40, "tokens": 11000}
  ],
  "by_source": {
    "web": {"requests": 30, "tokens": 8000},
    "api": {"requests": 12, "tokens": 4345}
  }
}`}
          />
        </section>
      </>
    ),
  },

  // ── Guides ──
  {
    slug: "guide-rag",
    label: "RAG Context Injection",
    section: "Guides",
    description: "How SLM augments answers with latest Solana/Anchor documentation.",
    content: (
      <>
        <section>
          <h2>How it works</h2>
          <p>
            For knowledge-type questions (not code generation), SLM queries a Qdrant vector index of
            latest Solana docs, Anchor source, SPL program docs, and community tech (Firedancer, ZK
            Compression, Token-2022). Relevance above 0.80 injects context into the system prompt.
          </p>
        </section>
        <section>
          <h2>Code-gen bypass</h2>
          <p>
            RAG is skipped for requests matching <code>write|create|build|implement|show|code|program|function|instruction</code>.
            This avoids the model feeling restricted to the retrieved snippets when composing full programs.
          </p>
        </section>
        <section>
          <h2>Sources</h2>
          <ul>
            <li>Solana docs (core, RPC, advanced)</li>
            <li>Anchor docs + changelog + source</li>
            <li>Solana Cookbook</li>
            <li>SPL program READMEs</li>
            <li>Metaplex (Token Metadata, Core, Bubblegum)</li>
            <li>SIMDs, Firedancer, ZK Compression, Jito, Marinade</li>
            <li>Solana Whitepaper</li>
          </ul>
        </section>
      </>
    ),
  },
  {
    slug: "guide-logit-bias",
    label: "Modern Anchor Enforcement",
    section: "Guides",
    description: "How SLM suppresses deprecated patterns at inference time.",
    content: (
      <>
        <section>
          <h2>The problem</h2>
          <p>
            Qwen2.5-Coder-7B-Instruct was trained on older Anchor examples that use <code>declare_id!</code>, which
            is deprecated in Anchor 0.30+. Even with a clear system prompt, the model defaults to the
            old pattern in ~90% of code-generation requests.
          </p>
        </section>
        <section>
          <h2>The fix</h2>
          <p>
            LiteLLM forwards <code>logit_bias: {"{"}&quot;18471&quot;: -30{"}"}</code> to SGLang. Token 18471 is
            the <code>declare</code> prefix in Qwen2.5&apos;s tokenizer. A bias of <code>-30</code> is strong
            enough that the model never emits <code>declare_id!</code> but soft enough that it still
            generates valid Rust.
          </p>
        </section>
        <section>
          <h2>Results</h2>
          <ul>
            <li>Before: ~60% of code samples contained <code>declare_id!</code></li>
            <li>After: 0/24 tests. All code compiles without modification.</li>
          </ul>
        </section>
      </>
    ),
  },
]

// ── Helpers ──

export function getAllDocSlugs(): string[] {
  return docTopics.map((t) => t.slug)
}

export function getDocTopic(slug: string): DocTopic | undefined {
  return docTopics.find((t) => t.slug === slug)
}

export function getAdjacentTopics(slug: string): {
  prev?: DocTopic
  next?: DocTopic
} {
  const idx = docTopics.findIndex((t) => t.slug === slug)
  return {
    prev: idx > 0 ? docTopics[idx - 1] : undefined,
    next: idx < docTopics.length - 1 ? docTopics[idx + 1] : undefined,
  }
}

/** Sidebar structure grouped by section */
export const docSections = (() => {
  const map = new Map<string, DocTopic[]>()
  for (const t of docTopics) {
    if (!map.has(t.section)) map.set(t.section, [])
    map.get(t.section)!.push(t)
  }
  return Array.from(map.entries()).map(([section, topics]) => ({
    section,
    topics,
  }))
})()
