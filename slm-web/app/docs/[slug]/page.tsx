import { notFound } from "next/navigation"
import type { Metadata } from "next"
import { PageLayout } from "@/components/shared/page-layout"
import { Card, CardContent } from "@/components/ui/card"
import { Breadcrumb } from "@/components/shared/breadcrumb"
import {
  getAllDocSlugs,
  getDocTopic,
  getAdjacentTopics,
  docSections,
} from "@/lib/docs-content"

interface PageProps {
  params: Promise<{ slug: string }>
}

export function generateStaticParams() {
  return getAllDocSlugs().map((slug) => ({ slug }))
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params
  const topic = getDocTopic(slug)
  if (!topic) return {}

  return {
    title: `${topic.label} — Sealevel Docs`,
    description: topic.description,
  }
}

export default async function DocTopicPage({ params }: PageProps) {
  const { slug } = await params
  const topic = getDocTopic(slug)
  if (!topic) notFound()

  const { prev, next } = getAdjacentTopics(slug)

  return (
    <PageLayout className="max-w-6xl">
      <div className="flex gap-8">
        {/* Sidebar */}
        <aside className="hidden w-48 shrink-0 lg:block">
          <nav className="sticky top-20 flex flex-col gap-6">
            {docSections.map((section) => (
              <div key={section.section}>
                <p className="mb-2 font-mono text-xs font-medium uppercase tracking-widest text-muted-foreground">
                  {section.section}
                </p>
                <ul className="flex flex-col gap-1">
                  {section.topics.map((item) => (
                    <li key={item.slug}>
                      <a
                        href={`/docs/${item.slug}`}
                        className={`block rounded-sm px-2 py-1 text-sm transition-colors ${
                          item.slug === slug
                            ? "bg-muted font-medium text-foreground"
                            : "text-muted-foreground hover:text-foreground"
                        }`}
                      >
                        {item.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </nav>
        </aside>

        {/* Content */}
        <main className="min-w-0 flex-1">
          <div className="mb-6">
            <Breadcrumb
              items={[
                { label: "Docs", href: "/docs" },
                { label: topic.label, href: `/docs/${slug}` },
              ]}
            />
          </div>
          <div className="mb-8 flex flex-col gap-2">
            <p className="font-mono text-xs font-medium uppercase tracking-widest text-muted-foreground">
              {topic.section}
            </p>
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
              {topic.label}
            </h1>
            <p className="text-sm text-muted-foreground">{topic.description}</p>
          </div>

          <Card>
            <CardContent className="prose prose-sm dark:prose-invert max-w-none pt-6 [&_h2]:mt-6 [&_h2]:mb-3 [&_h2]:text-lg [&_h2]:font-bold [&_section]:mb-6 [&_ul]:list-disc [&_ul]:pl-5 [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-xs [&_a]:underline [&_a]:underline-offset-2 [&_p]:leading-relaxed [&_p]:text-foreground/80">
              {topic.content}
            </CardContent>
          </Card>

          {/* Prev / Next navigation */}
          <div className="mt-8 flex items-center justify-between border-t pt-6">
            {prev ? (
              <a
                href={`/docs/${prev.slug}`}
                className="group flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                <span className="transition-transform group-hover:-translate-x-0.5">
                  &larr;
                </span>
                <span>
                  <span className="block font-mono text-xs uppercase tracking-widest">
                    Previous
                  </span>
                  <span className="font-medium text-foreground">
                    {prev.label}
                  </span>
                </span>
              </a>
            ) : (
              <div />
            )}
            {next ? (
              <a
                href={`/docs/${next.slug}`}
                className="group flex items-center gap-2 text-right text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                <span>
                  <span className="block font-mono text-xs uppercase tracking-widest">
                    Next
                  </span>
                  <span className="font-medium text-foreground">
                    {next.label}
                  </span>
                </span>
                <span className="transition-transform group-hover:translate-x-0.5">
                  &rarr;
                </span>
              </a>
            ) : (
              <div />
            )}
          </div>
        </main>
      </div>
    </PageLayout>
  )
}
