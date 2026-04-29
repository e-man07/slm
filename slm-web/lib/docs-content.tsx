import type { ReactNode } from "react"
import Link from "next/link"
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
          <h2>1. Install the CLI</h2>
          <CodeBlock language="bash" code={`pip install sealevel`} />
        </section>
        <section>
          <h2>2. Authenticate</h2>
          <CodeBlock language="bash" code={`slm login
# Opens your browser → sign in with GitHub or Google → done`} />
          <p>
            Or go to <Link href="/sign-in">sealevel.tech/sign-in</Link>, generate a key from the{" "}
            <Link href="/dashboard">Dashboard</Link>, and set it manually with{" "}
            <code>slm config --api-key slm_YOUR_KEY</code>.
          </p>
        </section>
        <section>
          <h2>3. Start chatting</h2>
          <CodeBlock language="bash" code={`slm                                    # interactive session
slm -p "How do I derive a PDA?"        # one-shot mode`} />
        </section>
        <section>
          <h2>4. Pick a client</h2>
          <p>Sealevel ships three clients — use whichever fits your workflow:</p>
          <ul>
            <li>
              <Link href="/docs/cli">CLI</Link> — interactive terminal session with slash commands
            </li>
            <li>
              <Link href="/docs/web">Web chat</Link> — no install, fastest way to try it
            </li>
            <li>
              <Link href="/docs/mcp">MCP server</Link> — Claude Code, Cursor, Windsurf integration
            </li>
          </ul>
        </section>
        <section>
          <h2>5. Raw API (curl)</h2>
          <CodeBlock
            language="bash"
            code={`curl https://www.sealevel.tech/api/chat \\
  -H "Authorization: Bearer slm_YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "messages": [{"role": "user", "content": "How do I derive a PDA in Anchor?"}],
    "max_tokens": 4096,
    "stream": true
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
    description: "OAuth sign-in, API keys, device login, rate-limit tiers.",
    content: (
      <>
        <section>
          <h2>OAuth providers</h2>
          <p>Sign in with GitHub or Google at <Link href="/sign-in">sealevel.tech/sign-in</Link>. Then go to the <Link href="/dashboard">Dashboard</Link> and click <strong>Generate API Key</strong> to create your key.</p>
        </section>
        <section>
          <h2>Device login (CLI)</h2>
          <p>
            The CLI supports browser-based authentication via the OAuth device flow.
            Run <code>slm login</code> — a device code appears in your terminal, your browser opens,
            and once you authenticate, the CLI receives your API key automatically.
          </p>
          <CodeBlock language="bash" code={`slm login
# Opens browser → sign in → CLI gets your key
# Key is stored securely in OS keyring`} />
          <p>You can also authenticate inside an active session with <code>/login</code>.</p>
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
          <h2>Key storage</h2>
          <p>
            The CLI stores your API key in the OS keyring (macOS Keychain, Windows Credential Locker,
            GNOME keyring/KWallet). Falls back to <code>~/.sealevel/config.toml</code> (chmod 600)
            if keyring is unavailable.
          </p>
        </section>
        <section>
          <h2>Rate-limit tiers</h2>
          <ul>
            <li><strong>Free</strong> (signed-in): 5 req/min, 100K tokens/day</li>
            <li><strong>Standard</strong>: 15 req/min, 500K tokens/day</li>
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
    description: "Use Sealevel directly at sealevel.tech/chat — no install needed.",
    content: (
      <>
        <section>
          <h2>What you get</h2>
          <ul>
            <li>Streaming chat with syntax-highlighted code blocks</li>
            <li>Chat history saved to your account (sign-in required)</li>
            <li>Transaction explainer at <Link href="/explain/tx">/explain/tx</Link></li>
            <li>Error decoder at <Link href="/explain/error">/explain/error</Link></li>
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
    description: "Interactive terminal session with slash commands for Solana/Anchor development.",
    content: (
      <>
        <section>
          <h2>Install</h2>
          <CodeBlock language="bash" code={`pip install sealevel
# Requires Python 3.10+`} />
        </section>
        <section>
          <h2>Authenticate</h2>
          <CodeBlock language="bash" code={`slm login          # Opens browser, authenticates via OAuth device flow
slm logout         # Clear stored credentials
slm config --show  # Verify your key is set`} />
          <p>
            Your API key is stored securely in the OS keyring. You can also set it manually
            with <code>slm config --api-key slm_YOUR_KEY</code>.
          </p>
        </section>
        <section>
          <h2>Interactive session</h2>
          <p>Run <code>slm</code> with no arguments to start an interactive session. Type plain text to chat, or use slash commands:</p>
          <CodeBlock language="bash" code={`$ slm
❯ How do I derive a PDA in Anchor?
◆ SEALEVEL
  To derive a PDA, use seeds and bump in your #[account] attribute...

❯ /review src/lib.rs
◆ REVIEWING  src/lib.rs
  ...

❯ /gen counter with increment and decrement -o src/lib.rs
✓ WROTE  src/lib.rs`} />
        </section>
        <section>
          <h2>Slash commands</h2>
          <p>Type <code>/</code> to see the live dropdown. 25 commands:</p>
          <ul>
            <li><strong>Code</strong></li>
            <li><code>/review &lt;file&gt;</code> — Security + deprecation review for Solana/Anchor code</li>
            <li><code>/migrate &lt;file&gt; [--write]</code> — Upgrade to modern Anchor 0.30+ patterns</li>
            <li><code>/gen &lt;description&gt; [-o file]</code> — Generate a complete Anchor program</li>
            <li><code>/tests &lt;file&gt; [-o out.ts]</code> — Generate TypeScript tests</li>
            <li><strong>Explain</strong></li>
            <li><code>/explain-tx &lt;signature&gt;</code> — Decode a Solana transaction</li>
            <li><code>/explain-error &lt;code&gt;</code> — Decode a Solana/Anchor error code</li>
            <li><strong>Session</strong></li>
            <li><code>/sessions</code> — List past sessions</li>
            <li><code>/resume &lt;id&gt;</code> — Resume a past session</li>
            <li><code>/rename &lt;name&gt;</code> — Rename current session</li>
            <li><code>/history</code> — Show conversation history</li>
            <li><code>/search &lt;query&gt;</code> — Search conversation history</li>
            <li><code>/compact [focus]</code> — AI-summarize old history to free context</li>
            <li><code>/export [file]</code> — Export session as markdown</li>
            <li><code>/clear</code> — Clear conversation history (with confirmation)</li>
            <li><code>/undo</code> — Undo last turn + restore modified files</li>
            <li><code>/retry</code> — Redo last turn with a fresh response</li>
            <li><strong>Info</strong></li>
            <li><code>/status</code> — API health + config overview</li>
            <li><code>/usage</code> — Token usage and limits</li>
            <li><code>/copy</code> — Copy last response to clipboard</li>
            <li><strong>System</strong></li>
            <li><code>/agent</code> — Toggle agent mode — experimental</li>
            <li><code>/login</code> — Authenticate via browser</li>
            <li><code>/config [--show]</code> — View or change settings</li>
            <li><code>/rotate-key</code> — Rotate API key</li>
            <li><code>/help</code> — Show all commands</li>
            <li><code>/exit</code> — Exit the session</li>
          </ul>
        </section>
        <section>
          <h2>Agent mode (experimental)</h2>
          <p>
            Toggle with <code>/agent</code>. The model can read files, search code,
            and run commands. Best with one action at a time:
          </p>
          <CodeBlock language="bash" code={`❯ /agent
✓ Agent mode ON

❯ read src/lib.rs and add an authority check
╭─ read_file ──────────────╮
│  path: src/lib.rs        │
│  ✓ 38 lines              │
╰──────────────────────────╯
╭─ edit_file ──────────────╮
│  path: src/lib.rs        │
│  -2 / +5 lines           │
╰──────────────────────────╯
▸ Allow edit? [y/N/a] y
✓ EDITED  src/lib.rs`} />
          <p>
            Read-only tools auto-approve. Write and execute tools ask permission.
            Type <code>a</code> to approve all of that type for the session.
            Use <code>/undo</code> to revert file changes.
          </p>
        </section>
        <section>
          <h2>Inline file references</h2>
          <p>Use <code>@path/to/file.rs</code> in chat to include file contents inline:</p>
          <CodeBlock language="bash" code={`❯ What's wrong with @src/lib.rs?
# File content is automatically injected into the prompt`} />
        </section>
        <section>
          <h2>Project memory</h2>
          <p>
            Create a <code>SEALEVEL.md</code> file in your project root (or <code>~/.sealevel/SEALEVEL.md</code>)
            to inject project-specific context into every prompt. The CLI walks from cwd to root looking for it.
          </p>
        </section>
        <section>
          <h2>Pipe mode</h2>
          <p>For scripting and CI, use <code>-p</code> for one-shot prompts:</p>
          <CodeBlock language="bash" code={`slm -p "What is a PDA?"                           # one-shot
cat src/lib.rs | slm -p "review this code"        # pipe stdin
slm -c                                            # continue last session`} />
        </section>
        <section>
          <h2>First-run onboarding</h2>
          <p>
            On first launch without an API key, the CLI prompts you to authenticate:
          </p>
          <CodeBlock language="bash" code={`$ slm
◆ Sealevel  v0.3.0  ·  sealevel.tech

Sign in to get started:

  1. Browser login (recommended)
  2. Paste API key manually

Choose [1/2]:`} />
          <p>
            Option 1 runs the device flow (same as <code>slm login</code>).
            Option 2 prompts for a key with masked input.
            You can skip and authenticate later with <code>/login</code> inside the session.
          </p>
        </section>
        <section>
          <h2>Modes</h2>
          <p>Switch between quality and fast inference:</p>
          <CodeBlock language="bash" code={`slm config --mode quality   # temp=0.0, 4096 max tokens (default)
slm config --mode fast      # temp=0.3, 2048 max tokens`} />
        </section>
        <section>
          <h2>Shell completion</h2>
          <CodeBlock language="bash" code={`slm --install-completion bash   # or zsh | fish`} />
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
            You need a Sealevel API key. <Link href="/sign-in">Sign in</Link>, then generate one from the{" "}
            <Link href="/dashboard">Dashboard</Link>.
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
          <p>
            Open Cursor Settings → MCP Servers, or edit <code>~/.cursor/mcp.json</code>{" "}
            directly (use <code>&lt;project&gt;/.cursor/mcp.json</code> for project-scoped
            install). Add:
          </p>
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
          <p>
            Open Windsurf Settings → MCP, or edit{" "}
            <code>~/.codeium/windsurf/mcp_config.json</code> directly. Add:
          </p>
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
    description: "POST /api/chat — SSE streaming chat endpoint.",
    content: (
      <>
        <section>
          <h2>Request</h2>
          <CodeBlock
            language="bash"
            code={`POST /api/chat
Authorization: Bearer slm_YOUR_KEY
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "Write an Anchor counter program"}
  ],
  "max_tokens": 4096,
  "temperature": 0.0,
  "stream": true
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
