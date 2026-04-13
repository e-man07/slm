import Link from "next/link"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  BubbleChatIcon,
  InspectCodeIcon,
  Alert01Icon,
  ApiIcon,
} from "@hugeicons/core-free-icons"
import { PageLayout } from "@/components/shared/page-layout"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { EvalCategoryChart } from "@/components/eval/eval-category-chart"
import evalData from "@/data/eval-results.json"

const FEATURES = [
  {
    icon: BubbleChatIcon,
    title: "Chat",
    description: "Ask anything about Solana & Anchor development",
    href: "/chat",
  },
  {
    icon: InspectCodeIcon,
    title: "Tx Explainer",
    description: "Paste a transaction signature, get a human-readable explanation",
    href: "/explain/tx",
  },
  {
    icon: Alert01Icon,
    title: "Error Decoder",
    description: "Decode Solana program errors with AI-powered fix suggestions",
    href: "/explain/error",
  },
  {
    icon: ApiIcon,
    title: "API Access",
    description: "OpenAI-compatible API for your tools and integrations",
    href: "/docs",
  },
] as const

export default function Page() {
  const categoryArray = Object.entries(evalData.categories)
    .map(([name, data]) => ({
      name,
      passed: (data as { passed: number }).passed,
      total: (data as { total: number }).total,
      score: (data as { score: number }).score,
    }))
    .sort((a, b) => {
      if (a.name === "adversarial") return 1
      if (b.name === "adversarial") return -1
      return b.score - a.score
    })

  return (
    <PageLayout>
      {/* Hero */}
      <section className="flex flex-col items-center gap-6 py-20 text-center">
        <Badge variant="outline" className="px-3 py-1">
          87.5% on 80 Solana coding tasks
        </Badge>
        <h1 className="max-w-2xl text-5xl font-bold tracking-tighter md:text-6xl">
          The Solana coding AI that actually knows Solana
        </h1>
        <p className="max-w-lg text-lg text-muted-foreground">
          Fine-tuned on 741K Solana records. Chat, explain transactions, decode
          errors. In your browser, terminal, or editor.
        </p>
        <div className="flex gap-3">
          <Button size="lg" asChild>
            <Link href="/chat">Try it now</Link>
          </Button>
          <Button size="lg" variant="outline" asChild>
            <Link href="/dashboard">API Docs</Link>
          </Button>
        </div>
      </section>

      {/* Features */}
      <section className="grid gap-4 py-12 md:grid-cols-2">
        {FEATURES.map((feature) => (
          <Link key={feature.href} href={feature.href}>
            <Card className="h-full transition-colors hover:border-foreground/20">
              <CardHeader className="flex flex-row items-center gap-3 pb-2">
                <div className="flex size-10 items-center justify-center border border-border bg-muted">
                  <HugeiconsIcon icon={feature.icon} size={20} />
                </div>
                <CardTitle className="text-base">{feature.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  {feature.description}
                </p>
              </CardContent>
            </Card>
          </Link>
        ))}
      </section>

      {/* Install */}
      <section className="py-12">
        <h2 className="mb-6 text-center text-2xl font-bold">Get started</h2>
        <Tabs defaultValue="cli" className="mx-auto max-w-lg">
          <TabsList className="w-full">
            <TabsTrigger value="cli" className="flex-1">CLI</TabsTrigger>
            <TabsTrigger value="api" className="flex-1">API</TabsTrigger>
            <TabsTrigger value="ollama" className="flex-1">Ollama</TabsTrigger>
            <TabsTrigger value="vscode" className="flex-1">VS Code</TabsTrigger>
          </TabsList>
          <TabsContent value="cli">
            <Card>
              <CardContent className="pt-4">
                <pre className="overflow-x-auto bg-muted p-4 text-sm">
                  <code>pip install slm-cli{"\n"}slm chat &quot;How do I create a PDA?&quot;</code>
                </pre>
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="api">
            <Card>
              <CardContent className="pt-4">
                <pre className="overflow-x-auto bg-muted p-4 text-sm">
                  <code>{`curl -X POST https://slm.dev/api/chat \\
  -H "Content-Type: application/json" \\
  -d '{"messages": [{"role": "user",
    "content": "Write a PDA in Anchor"}],
  "stream": true}'`}</code>
                </pre>
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="ollama">
            <Card>
              <CardContent className="pt-4">
                <pre className="overflow-x-auto bg-muted p-4 text-sm">
                  <code>ollama run slm-solana{"\n"}&gt;&gt;&gt; How do I create a PDA in Anchor?</code>
                </pre>
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="vscode">
            <Card>
              <CardContent className="pt-4">
                <pre className="overflow-x-auto bg-muted p-4 text-sm">
                  <code>ext install slm.slm-solana</code>
                </pre>
                <p className="mt-2 text-xs text-muted-foreground">
                  Search &quot;SLM Solana&quot; in the VS Code Extensions marketplace
                </p>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </section>

      {/* Eval */}
      <section className="py-12">
        <div className="mb-6 text-center">
          <h2 className="text-2xl font-bold">Evaluation Results</h2>
          <p className="mt-1 text-muted-foreground">
            80-task benchmark across 7 Solana/Anchor categories
          </p>
        </div>
        <Card className="mx-auto max-w-lg">
          <CardContent className="pt-6">
            <div className="mb-6 text-center">
              <div className="text-4xl font-bold tabular-nums">
                {Math.round(evalData.overall.score * 1000) / 10}%
              </div>
              <p className="text-sm text-muted-foreground">
                {evalData.overall.passed}/{evalData.overall.total} tasks passed
              </p>
            </div>
            <EvalCategoryChart categories={categoryArray} />
            <div className="mt-4 text-center">
              <Button variant="outline" size="sm" asChild>
                <Link href="/eval">View full results</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </section>
    </PageLayout>
  )
}
