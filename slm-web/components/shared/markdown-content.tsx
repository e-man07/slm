"use client"

import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { CopyButton } from "@/components/shared/copy-button"

function CodeBlock({ code, language }: { code: string; language: string }) {
  const labels: Record<string, string> = {
    rust: "RUST", typescript: "TYPESCRIPT", ts: "TYPESCRIPT",
    javascript: "JAVASCRIPT", js: "JAVASCRIPT", toml: "TOML",
    json: "JSON", bash: "BASH", python: "PYTHON",
  }
  return (
    <div className="my-3.5 border border-border terminal-bg">
      <div className="flex items-center justify-between border-b border-border px-3 py-1.5">
        <span className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
          {labels[language] ?? language.toUpperCase()}
        </span>
        <CopyButton value={code} />
      </div>
      <pre className="overflow-x-auto p-3.5 text-xs leading-[1.7]">
        <code>{code}</code>
      </pre>
    </div>
  )
}

interface MarkdownContentProps {
  content: string
  isStreaming?: boolean
}

export function MarkdownContent({ content, isStreaming }: MarkdownContentProps) {
  return (
    <div className="text-[13.5px] leading-[1.7]">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || "")
            const codeString = String(children).replace(/\n$/, "")
            if (match) return <CodeBlock code={codeString} language={match[1]} />
            const isBlock = className !== undefined || codeString.includes("\n")
            if (isBlock) return <CodeBlock code={codeString} language="text" />
            return (
              <code className="bg-muted px-1.5 py-0.5 text-xs text-foreground" {...props}>
                {children}
              </code>
            )
          },
          pre({ children }) { return <>{children}</> },
          a({ href, children, ...props }) {
            return <a href={href} target="_blank" rel="noopener noreferrer" className="slm-accent underline underline-offset-2" {...props}>{children}</a>
          },
          ul({ children, ...props }) { return <ul className="my-2 ml-5 list-disc space-y-1" {...props}>{children}</ul> },
          ol({ children, ...props }) { return <ol className="my-2 ml-5 list-decimal space-y-1" {...props}>{children}</ol> },
          strong({ children, ...props }) { return <strong className="text-foreground font-semibold" {...props}>{children}</strong> },
          p({ children, ...props }) { return <p className="mb-2.5 last:mb-0" {...props}>{children}</p> },
          li({ children, ...props }) { return <li className="my-1" {...props}>{children}</li> },
        }}
      >
        {content}
      </ReactMarkdown>
      {isStreaming && <span className="cursor-blink ml-0.5" />}
    </div>
  )
}
