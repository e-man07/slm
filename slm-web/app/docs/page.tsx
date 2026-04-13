import Link from "next/link"
import { PageLayout } from "@/components/shared/page-layout"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { CodeBlock } from "@/components/shared/code-block"

const TRY_IT_PROMPTS = [
  "How do I create a PDA in Anchor?",
  "Write an SPL token transfer in Anchor 0.30+",
  "Explain error 0x1771",
] as const

function Section({
  id,
  title,
  children,
}: {
  id: string
  title: string
  children: React.ReactNode
}) {
  return (
    <section id={id} className="scroll-mt-20 space-y-4">
      <h2 className="text-xl font-bold">{title}</h2>
      {children}
    </section>
  )
}

const NAV_ITEMS = [
  { id: "auth", label: "Authentication" },
  { id: "chat", label: "Chat" },
  { id: "tx", label: "Tx Explainer" },
  { id: "error", label: "Error Decoder" },
  { id: "health", label: "Health" },
  { id: "rate-limits", label: "Rate Limits" },
  { id: "errors", label: "Error Codes" },
  { id: "sdks", label: "SDKs" },
]

export default function DocsPage() {
  return (
    <PageLayout className="max-w-6xl">
      <div className="flex gap-8">
        {/* Sidebar */}
        <nav className="hidden w-48 shrink-0 md:block">
          <div className="sticky top-20 space-y-1">
            <p className="mb-2 text-sm font-medium">API Reference</p>
            {NAV_ITEMS.map((item) => (
              <a
                key={item.id}
                href={`#${item.id}`}
                className="block py-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                {item.label}
              </a>
            ))}
          </div>
        </nav>

        {/* Content */}
        <div className="min-w-0 flex-1 space-y-10">
          <div>
            <h1 className="text-3xl font-bold">API Documentation</h1>
            <p className="mt-2 text-muted-foreground">
              OpenAI-compatible API for Solana development assistance
            </p>
            <div className="mt-3 flex items-center gap-2">
              <Badge variant="outline">Base URL</Badge>
              <code className="text-sm">https://slm.dev/api</code>
            </div>
          </div>

          <Separator />

          {/* Auth */}
          <Section id="auth" title="Authentication">
            <p className="text-sm text-muted-foreground">
              All endpoints accept an optional API key via the Authorization header.
              Without auth, anonymous rate limits apply (5 req/min, 10K tokens/day).
            </p>
            <CodeBlock
              code={`curl -H "Authorization: Bearer slm_xxxxxxxxxxxx" \\
  https://slm.dev/api/chat`}
              language="bash"
            />
          </Section>

          <Separator />

          {/* Chat */}
          <Section id="chat" title="POST /api/chat">
            <p className="text-sm text-muted-foreground">
              Stream or non-stream chat completions. OpenAI-compatible format.
            </p>

            <Tabs defaultValue="request">
              <TabsList>
                <TabsTrigger value="request">Request</TabsTrigger>
                <TabsTrigger value="response">Response</TabsTrigger>
                <TabsTrigger value="streaming">Streaming</TabsTrigger>
              </TabsList>
              <TabsContent value="request">
                <CodeBlock
                  code={`{
  "messages": [
    {"role": "user", "content": "How do I create a PDA in Anchor?"}
  ],
  "stream": true,
  "max_tokens": 1024,
  "temperature": 0.0
}`}
                  language="json"
                  filename="Request Body"
                />
              </TabsContent>
              <TabsContent value="response">
                <CodeBlock
                  code={`{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "In Anchor 0.30+, you derive a PDA using seeds..."
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 45,
    "completion_tokens": 312,
    "total_tokens": 357
  }
}`}
                  language="json"
                  filename="Response (stream: false)"
                />
              </TabsContent>
              <TabsContent value="streaming">
                <CodeBlock
                  code={`data: {"choices":[{"delta":{"role":"assistant"},"index":0}]}

data: {"choices":[{"delta":{"content":"In"},"index":0}]}

data: {"choices":[{"delta":{"content":" Anchor"},"index":0}]}

data: [DONE]`}
                  language="text"
                  filename="SSE Stream (stream: true)"
                />
              </TabsContent>
            </Tabs>

            <div className="mt-4 space-y-2">
              <p className="text-sm text-muted-foreground">Try it in the chat:</p>
              <div className="flex flex-wrap gap-2">
                {TRY_IT_PROMPTS.map((prompt) => (
                  <Link
                    key={prompt}
                    href={`/chat?prompt=${encodeURIComponent(prompt)}`}
                    className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium transition-colors hover:bg-accent"
                  >
                    Try it: {prompt.length > 40 ? `${prompt.slice(0, 40)}...` : prompt}
                  </Link>
                ))}
              </div>
            </div>
          </Section>

          <Separator />

          {/* Tx Explainer */}
          <Section id="tx" title="POST /api/explain/tx">
            <p className="text-sm text-muted-foreground">
              Explain a Solana transaction in human-readable format. Returns
              structured data followed by a streamed AI explanation.
            </p>
            <Tabs defaultValue="request">
              <TabsList>
                <TabsTrigger value="request">Request</TabsTrigger>
                <TabsTrigger value="response">Response</TabsTrigger>
              </TabsList>
              <TabsContent value="request">
                <CodeBlock
                  code={`{
  "signature": "5UfDuX7WXYxjng1PYLJm..."
}`}
                  language="json"
                  filename="Request Body"
                />
              </TabsContent>
              <TabsContent value="response">
                <CodeBlock
                  code={`data: {"type":"tx_data","data":{"status":"success","type":"SWAP","fee":0.000005,...}}

data: {"type":"content","content":"This transaction"}

data: {"type":"content","content":" performs a token swap"}

data: [DONE]`}
                  language="text"
                  filename="SSE Stream"
                />
              </TabsContent>
            </Tabs>
          </Section>

          <Separator />

          {/* Error Decoder */}
          <Section id="error" title="POST /api/explain/error">
            <p className="text-sm text-muted-foreground">
              Decode a Solana program error code. Returns a static lookup result
              followed by a streamed AI explanation.
            </p>
            <Tabs defaultValue="request">
              <TabsList>
                <TabsTrigger value="request">Request</TabsTrigger>
                <TabsTrigger value="response">Response</TabsTrigger>
              </TabsList>
              <TabsContent value="request">
                <CodeBlock
                  code={`{
  "error_code": "0x1771",
  "program_id": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
}`}
                  language="json"
                  filename="Request Body"
                />
              </TabsContent>
              <TabsContent value="response">
                <CodeBlock
                  code={`data: {"type":"lookup","data":{"program_name":"SPL Token","error_name":"InsufficientFunds",...}}

data: {"type":"content","content":"This error occurs when"}

data: [DONE]`}
                  language="text"
                  filename="SSE Stream"
                />
              </TabsContent>
            </Tabs>
          </Section>

          <Separator />

          {/* Health */}
          <Section id="health" title="GET /api/health">
            <CodeBlock
              code={`{
  "status": "ok",
  "sglang": true,
  "timestamp": "2026-04-05T12:00:00Z"
}`}
              language="json"
              filename="Response"
            />
          </Section>

          <Separator />

          {/* Rate Limits */}
          <Section id="rate-limits" title="Rate Limits">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Tier</TableHead>
                  <TableHead>Requests/min</TableHead>
                  <TableHead>Tokens/day</TableHead>
                  <TableHead>Access</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow>
                  <TableCell>Anonymous</TableCell>
                  <TableCell>5</TableCell>
                  <TableCell>10K</TableCell>
                  <TableCell>No signup</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Free</TableCell>
                  <TableCell>10</TableCell>
                  <TableCell>50K</TableCell>
                  <TableCell>GitHub OAuth</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Standard</TableCell>
                  <TableCell>30</TableCell>
                  <TableCell>500K</TableCell>
                  <TableCell>Applied</TableCell>
                </TableRow>
              </TableBody>
            </Table>
            <p className="mt-3 text-sm text-muted-foreground">
              Rate limit headers are returned with every response:
            </p>
            <CodeBlock
              code={`X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1712345678`}
              language="text"
              filename="Response Headers"
            />
          </Section>

          <Separator />

          {/* Error Codes */}
          <Section id="errors" title="Error Codes">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Description</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow>
                  <TableCell><code>unauthorized</code></TableCell>
                  <TableCell>401</TableCell>
                  <TableCell>Invalid or missing API key</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell><code>rate_limited</code></TableCell>
                  <TableCell>429</TableCell>
                  <TableCell>Rate limit exceeded</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell><code>invalid_input</code></TableCell>
                  <TableCell>400</TableCell>
                  <TableCell>Bad request format</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell><code>model_unavailable</code></TableCell>
                  <TableCell>503</TableCell>
                  <TableCell>Inference server unreachable</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell><code>tx_not_found</code></TableCell>
                  <TableCell>404</TableCell>
                  <TableCell>Transaction signature not found</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell><code>helius_error</code></TableCell>
                  <TableCell>502</TableCell>
                  <TableCell>Helius API failure</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell><code>upstream_timeout</code></TableCell>
                  <TableCell>504</TableCell>
                  <TableCell>Upstream inference server timed out</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </Section>

          <Separator />

          {/* SDKs */}
          <Section id="sdks" title="SDK Examples">
            <Tabs defaultValue="python">
              <TabsList>
                <TabsTrigger value="python">Python</TabsTrigger>
                <TabsTrigger value="typescript">TypeScript</TabsTrigger>
                <TabsTrigger value="curl">cURL</TabsTrigger>
              </TabsList>
              <TabsContent value="python">
                <CodeBlock
                  code={`import httpx

response = httpx.post(
    "https://slm.dev/api/chat",
    headers={"Authorization": "Bearer slm_xxxx"},
    json={
        "messages": [{"role": "user", "content": "Write a PDA in Anchor"}],
        "stream": True,
    },
)

for line in response.iter_lines():
    if line.startswith("data: ") and line != "data: [DONE]":
        import json
        data = json.loads(line[6:])
        content = data["choices"][0]["delta"].get("content", "")
        print(content, end="", flush=True)`}
                  language="typescript"
                  filename="python_example.py"
                />
              </TabsContent>
              <TabsContent value="typescript">
                <CodeBlock
                  code={`const response = await fetch("https://slm.dev/api/chat", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": "Bearer slm_xxxx",
  },
  body: JSON.stringify({
    messages: [{ role: "user", content: "Write a PDA in Anchor" }],
    stream: true,
  }),
});

const reader = response.body!.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  const text = decoder.decode(value);
  process.stdout.write(text);
}`}
                  language="typescript"
                  filename="example.ts"
                />
              </TabsContent>
              <TabsContent value="curl">
                <CodeBlock
                  code={`curl -X POST https://slm.dev/api/chat \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer slm_xxxx" \\
  -d '{
    "messages": [{"role": "user", "content": "Write a PDA in Anchor"}],
    "stream": true
  }'`}
                  language="bash"
                  filename="Terminal"
                />
              </TabsContent>
            </Tabs>
          </Section>
        </div>
      </div>
    </PageLayout>
  )
}
