import type { Metadata } from "next"
import { PageLayout } from "@/components/shared/page-layout"
import { docSections } from "@/lib/docs-content"

export const metadata: Metadata = {
  title: "Docs — Sealevel",
  description:
    "API reference, client setup guides, and architecture docs for Sealevel — the Solana-specialized coding LLM.",
}

export default function DocsPage() {
  return (
    <PageLayout className="max-w-6xl">
      <div className="mb-10 flex flex-col gap-3">
        <p className="font-mono text-sm font-medium uppercase tracking-widest text-muted-foreground">
          Documentation
        </p>
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
          Sealevel Docs
        </h1>
        <p className="max-w-lg text-muted-foreground">
          Set up CLI, VS Code, MCP, or hit the API directly. Guides for every
          integration point.
        </p>
      </div>

      <div className="flex flex-col gap-10">
        {docSections.map((section) => (
          <div key={section.section}>
            <h2 className="mb-6 text-xl font-bold tracking-tight">
              {section.section}
            </h2>
            <div className="grid gap-4 sm:grid-cols-2">
              {section.topics.map((item) => (
                <a
                  key={item.slug}
                  href={`/docs/${item.slug}`}
                  className="border p-5 transition-colors hover:border-foreground/20 hover:bg-muted/50"
                >
                  <h3 className="text-sm font-bold">{item.label}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                    {item.description}
                  </p>
                </a>
              ))}
            </div>
          </div>
        ))}
      </div>
    </PageLayout>
  )
}
