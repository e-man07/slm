"use client"

import * as React from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { cn } from "@/lib/utils"
import { CopyButton } from "@/components/shared/copy-button"
import { HugeiconsIcon } from "@hugeicons/react"
import { ThumbsUpIcon, ThumbsDownIcon } from "@hugeicons/core-free-icons"
import type { ChatMessage as ChatMessageType } from "@/hooks/use-chat"

interface ChatMessageProps {
  message: ChatMessageType
  onFeedback?: (messageId: string, feedback: "up" | "down" | null) => void
}

function CodeBlockClient({ code, language }: { code: string; language: string }) {
  const languageLabels: Record<string, string> = {
    rust: "Rust",
    typescript: "TypeScript",
    ts: "TypeScript",
    javascript: "JavaScript",
    js: "JavaScript",
    toml: "TOML",
    json: "JSON",
    bash: "Bash",
  }

  return (
    <div className="group relative my-3 border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <span className="text-xs text-muted-foreground">
          {languageLabels[language] ?? language}
        </span>
        <CopyButton value={code} />
      </div>
      <pre className="overflow-x-auto p-4 text-sm">
        <code>{code}</code>
      </pre>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div data-testid="typing-indicator" className="flex items-center gap-1 py-1">
      <span className="inline-block h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:0ms]" />
      <span className="inline-block h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:150ms]" />
      <span className="inline-block h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:300ms]" />
    </div>
  )
}

function FeedbackButtons({
  messageId,
  feedback,
  onFeedbackChange,
}: {
  messageId: string
  feedback?: "up" | "down"
  onFeedbackChange: (feedback: "up" | "down" | null) => void
}) {
  return (
    <div className="flex items-center gap-1">
      <button
        aria-label="Thumbs up"
        data-active={feedback === "up" ? "true" : undefined}
        onClick={() => onFeedbackChange(feedback === "up" ? null : "up")}
        className={cn(
          "rounded p-1 transition-colors hover:bg-muted",
          feedback === "up"
            ? "text-chart-1"
            : feedback === "down"
              ? "text-muted-foreground/30"
              : "text-muted-foreground",
        )}
      >
        <HugeiconsIcon icon={ThumbsUpIcon} size={14} />
      </button>
      <button
        aria-label="Thumbs down"
        data-active={feedback === "down" ? "true" : undefined}
        onClick={() => onFeedbackChange(feedback === "down" ? null : "down")}
        className={cn(
          "rounded p-1 transition-colors hover:bg-muted",
          feedback === "down"
            ? "text-destructive"
            : feedback === "up"
              ? "text-muted-foreground/30"
              : "text-muted-foreground",
        )}
      >
        <HugeiconsIcon icon={ThumbsDownIcon} size={14} />
      </button>
    </div>
  )
}

function MessageContent({
  content,
  isStreaming,
}: {
  content: string
  isStreaming?: boolean
}) {
  if (isStreaming && !content) {
    return <TypingIndicator />
  }

  return (
    <div className="prose-sm max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || "")
            const codeString = String(children).replace(/\n$/, "")

            // Fenced code block (has language class from markdown)
            if (match) {
              return (
                <CodeBlockClient code={codeString} language={match[1]} />
              )
            }

            // Check if this is a block-level code (inside <pre>)
            // react-markdown wraps fenced code blocks in <pre><code>
            // For inline code, there's no <pre> wrapper
            const isBlock =
              className !== undefined ||
              codeString.includes("\n")

            if (isBlock) {
              return (
                <CodeBlockClient code={codeString} language="text" />
              )
            }

            // Inline code
            return (
              <code className="rounded bg-muted px-1.5 py-0.5 text-sm" {...props}>
                {children}
              </code>
            )
          },
          pre({ children }) {
            // Let the code component handle rendering
            return <>{children}</>
          },
          a({ href, children, ...props }) {
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary underline underline-offset-2 hover:text-primary/80"
                {...props}
              >
                {children}
              </a>
            )
          },
          ul({ children, ...props }) {
            return (
              <ul className="my-2 ml-4 list-disc space-y-1" {...props}>
                {children}
              </ul>
            )
          },
          ol({ children, ...props }) {
            return (
              <ol className="my-2 ml-4 list-decimal space-y-1" {...props}>
                {children}
              </ol>
            )
          },
          h1({ children, ...props }) {
            return <h1 className="mb-2 mt-4 text-lg font-bold" {...props}>{children}</h1>
          },
          h2({ children, ...props }) {
            return <h2 className="mb-2 mt-3 text-base font-bold" {...props}>{children}</h2>
          },
          h3({ children, ...props }) {
            return <h3 className="mb-1 mt-2 text-sm font-bold" {...props}>{children}</h3>
          },
          p({ children, ...props }) {
            return <p className="my-1" {...props}>{children}</p>
          },
        }}
      >
        {content}
      </ReactMarkdown>
      {isStreaming && (
        <span className="ml-0.5 inline-block h-4 w-[2px] animate-pulse bg-foreground" />
      )}
    </div>
  )
}

export function ChatMessage({ message, onFeedback }: ChatMessageProps) {
  const isUser = message.role === "user"
  const [localFeedback, setLocalFeedback] = React.useState<"up" | "down" | null>(
    message.feedback ?? null,
  )

  const handleFeedback = React.useCallback(
    (feedback: "up" | "down" | null) => {
      setLocalFeedback(feedback)
      onFeedback?.(message.id, feedback)
    },
    [message.id, onFeedback],
  )

  return (
    <div
      data-slot="chat-message"
      className={cn(
        "flex w-full gap-3",
        isUser ? "justify-end" : "justify-start",
      )}
    >
      <div
        className={cn(
          "max-w-[85%] px-4 py-3 text-sm leading-relaxed",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-card border border-border",
        )}
      >
        <MessageContent
          content={message.content}
          isStreaming={message.isStreaming}
        />
        {!isUser && !message.isStreaming && message.content && (
          <div className="mt-2 flex items-center justify-between">
            <FeedbackButtons
              messageId={message.id}
              feedback={localFeedback ?? undefined}
              onFeedbackChange={handleFeedback}
            />
            <CopyButton value={message.content} />
          </div>
        )}
      </div>
    </div>
  )
}
