import type { Metadata } from "next"
import Link from "next/link"
import { NavBar } from "@/components/nav-bar"
import { docSections, docTopics } from "@/lib/docs-content"

export const metadata: Metadata = {
  title: "Docs — Sealevel",
  description:
    "API reference, client setup guides, and architecture docs for Sealevel — the Solana-specialized coding LLM.",
}

const SECTION_NUMBERS: Record<string, string> = {
  "Getting Started": "01",
  Clients: "02",
  "API Reference": "03",
  Guides: "04",
}

export default function DocsPage() {
  const firstTopic = docTopics[0]

  return (
    <>
      <NavBar />

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "240px 1fr",
          minHeight: "calc(100vh - 57px)",
          maxWidth: 1200,
          margin: "0 auto",
          width: "100%",
        }}
      >
        {/* ── Sidebar ── */}
        <aside
          style={{
            position: "sticky",
            top: 57,
            height: "calc(100vh - 57px)",
            borderRight: "1px solid var(--border)",
            padding: "40px 24px",
            overflowY: "auto",
          }}
        >
          <nav style={{ display: "flex", flexDirection: "column", gap: 28 }}>
            {docSections.map((section) => {
              const num = SECTION_NUMBERS[section.section] ?? "00"
              return (
                <div key={section.section}>
                  {/* Section title */}
                  <p
                    style={{
                      fontSize: 10,
                      textTransform: "uppercase",
                      letterSpacing: "0.12em",
                      color: "var(--muted-foreground)",
                      marginBottom: 10,
                      fontWeight: 500,
                    }}
                  >
                    <span style={{ color: "var(--slm-accent)" }}>{num}</span>{" "}
                    {section.section}
                  </p>

                  {/* Doc links */}
                  <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
                    {section.topics.map((item) => {
                      const isActive = item.slug === firstTopic.slug
                      const topicIdx = docTopics.findIndex(
                        (t) => t.slug === item.slug,
                      )
                      const prefix = String(topicIdx + 1).padStart(2, "0")
                      return (
                        <li key={item.slug}>
                          <Link
                            href={`/docs/${item.slug}`}
                            style={{
                              display: "block",
                              padding: "6px 10px",
                              margin: "0 -10px",
                              fontSize: 12.5,
                              color: isActive
                                ? "var(--foreground)"
                                : "var(--muted-foreground)",
                              borderLeft: `2px solid ${isActive ? "var(--slm-accent)" : "transparent"}`,
                              background: isActive
                                ? "var(--muted)"
                                : "transparent",
                              textDecoration: "none",
                              transition: "color 0.15s, background 0.15s",
                            }}
                          >
                            <span
                              style={{
                                fontSize: 10,
                                color: isActive
                                  ? "var(--slm-accent)"
                                  : "var(--slm-border-strong)",
                                marginRight: 6,
                              }}
                            >
                              {prefix}
                            </span>
                            {item.label}
                          </Link>
                        </li>
                      )
                    })}
                  </ul>
                </div>
              )
            })}
          </nav>
        </aside>

        {/* ── Main content ── */}
        <main
          style={{
            padding: "56px 56px 100px",
            maxWidth: 820,
          }}
        >
          {/* Breadcrumbs */}
          <p
            style={{
              fontSize: 11,
              textTransform: "uppercase",
              letterSpacing: "0.12em",
              color: "var(--muted-foreground)",
              marginBottom: 16,
            }}
          >
            <span>Docs</span>
            <span style={{ margin: "0 8px", opacity: 0.4 }}>/</span>
            <span>Getting Started</span>
            <span style={{ margin: "0 8px", opacity: 0.4 }}>/</span>
            <span style={{ color: "var(--foreground)" }}>Overview</span>
          </p>

          {/* Heading */}
          <h1
            style={{
              fontSize: 40,
              fontWeight: 700,
              letterSpacing: "-0.02em",
              lineHeight: 1.1,
              marginBottom: 12,
            }}
          >
            Sealevel Docs.
          </h1>

          {/* Subtitle */}
          <p
            style={{
              fontSize: 14,
              lineHeight: 1.75,
              color: "var(--muted-foreground)",
              maxWidth: 540,
              marginBottom: 48,
            }}
          >
            Set up CLI, MCP, or hit the API directly. Guides for every
            integration point.
          </p>

          {/* ── TOC grid ── */}
          {docSections.map((section) => {
            const num = SECTION_NUMBERS[section.section] ?? "00"
            return (
              <div key={section.section} style={{ marginTop: 56 }}>
                {/* Section heading with accent dash */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    marginBottom: 20,
                  }}
                >
                  <span
                    style={{
                      width: 20,
                      height: 1,
                      background: "var(--slm-accent)",
                      flexShrink: 0,
                    }}
                  />
                  <h2
                    style={{
                      fontSize: 14,
                      textTransform: "uppercase",
                      letterSpacing: "0.12em",
                      color: "var(--muted-foreground)",
                      fontWeight: 500,
                      margin: 0,
                      whiteSpace: "nowrap",
                    }}
                  >
                    <span className="slm-accent" style={{ marginRight: 8 }}>
                      {num}
                    </span>
                    {section.section}
                  </h2>
                  <span
                    style={{
                      flex: 1,
                      height: 1,
                      background: "var(--border)",
                    }}
                  />
                </div>

                {/* Grid of topic cards */}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: `repeat(${Math.min(section.topics.length, 3)}, 1fr)`,
                  }}
                >
                  {section.topics.map((item) => {
                    const topicIdx = docTopics.findIndex(
                      (t) => t.slug === item.slug,
                    )
                    const prefix = String(topicIdx + 1).padStart(2, "0")
                    return (
                      <Link
                        key={item.slug}
                        href={`/docs/${item.slug}`}
                        style={{
                          display: "block",
                          border: "1px solid var(--border)",
                          padding: "20px 18px",
                          textDecoration: "none",
                          color: "inherit",
                          transition:
                            "border-color 0.15s, background 0.15s",
                          marginRight: -1,
                          marginBottom: -1,
                        }}
                        className="docs-grid-cell"
                      >
                        <p
                          style={{
                            fontSize: 10,
                            textTransform: "uppercase",
                            letterSpacing: "0.1em",
                            color: "var(--slm-border-strong)",
                            marginBottom: 6,
                          }}
                        >
                          {prefix}
                        </p>
                        <p
                          style={{
                            fontSize: 14,
                            fontWeight: 600,
                            marginBottom: 6,
                          }}
                        >
                          {item.label}
                        </p>
                        <p
                          style={{
                            fontSize: 12.5,
                            lineHeight: 1.6,
                            color: "var(--muted-foreground)",
                            margin: 0,
                          }}
                        >
                          {item.description}
                        </p>
                      </Link>
                    )
                  })}
                </div>
              </div>
            )
          })}

          {/* ── Callout ── */}
          <div
            style={{
              marginTop: 56,
              borderLeft: "2px solid var(--slm-accent)",
              background: "var(--muted)",
              padding: "16px 20px",
            }}
          >
            <p
              style={{
                fontSize: 10,
                textTransform: "uppercase",
                letterSpacing: "0.12em",
                color: "var(--slm-accent)",
                fontWeight: 600,
                marginBottom: 6,
              }}
            >
              Heads Up
            </p>
            <p
              style={{
                fontSize: 14,
                lineHeight: 1.75,
                color: "var(--muted-foreground)",
                margin: 0,
              }}
            >
              Sealevel is under active development. APIs and clients may change.
              Star the{" "}
              <a
                href="https://github.com/e-man07/slm"
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  color: "var(--foreground)",
                  textDecoration: "underline",
                  textUnderlineOffset: 3,
                }}
              >
                GitHub repo
              </a>{" "}
              for updates.
            </p>
          </div>

          {/* ── Bottom nav ── */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 0,
              marginTop: 56,
            }}
          >
            <div />
            <Link
              href={`/docs/${firstTopic.slug}`}
              className="docs-nav-card"
              style={{
                display: "block",
                border: "1px solid var(--border)",
                padding: "20px 24px",
                textDecoration: "none",
                color: "inherit",
                textAlign: "right",
                transition: "border-color 0.15s",
              }}
            >
              <p
                style={{
                  fontSize: 10,
                  textTransform: "uppercase",
                  letterSpacing: "0.12em",
                  color: "var(--muted-foreground)",
                  marginBottom: 4,
                }}
              >
                Next
              </p>
              <p style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>
                {firstTopic.label} &rarr;
              </p>
            </Link>
          </div>
        </main>
      </div>

      {/* Hover styles for grid cells and nav cards */}
      <style>{`
        .docs-grid-cell:hover {
          border-color: var(--slm-accent) !important;
          background: var(--muted);
        }
        .docs-nav-card:hover {
          border-color: var(--slm-accent) !important;
        }
      `}</style>
    </>
  )
}
