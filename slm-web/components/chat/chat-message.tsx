"use client"

import * as React from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { useSession } from "next-auth/react"
import { cn } from "@/lib/utils"
import { CopyButton } from "@/components/shared/copy-button"
import type { ChatMessage as ChatMessageType } from "@/hooks/use-chat"

interface ChatMessageProps {
  message: ChatMessageType
  onFeedback?: (messageId: string, feedback: "up" | "down" | null) => void
}

function CodeBlockClient({ code, language }: { code: string; language: string }) {
  const languageLabels: Record<string, string> = {
    rust: "RUST",
    typescript: "TYPESCRIPT",
    ts: "TYPESCRIPT",
    javascript: "JAVASCRIPT",
    js: "JAVASCRIPT",
    toml: "TOML",
    json: "JSON",
    bash: "BASH",
  }

  return (
    <div className="group relative my-3.5 border border-border terminal-bg">
      <div className="flex items-center justify-between border-b border-border px-3 py-1.5">
        <span className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
          {languageLabels[language] ?? language.toUpperCase()}
        </span>
        <CopyButton value={code} />
      </div>
      <pre className="overflow-x-auto p-3.5 text-xs leading-[1.7]">
        <code>{code}</code>
      </pre>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div data-testid="typing-indicator" className="flex items-center gap-1 py-1">
      <span className="inline-block h-2 w-2 animate-bounce bg-muted-foreground [animation-delay:0ms]" />
      <span className="inline-block h-2 w-2 animate-bounce bg-muted-foreground [animation-delay:150ms]" />
      <span className="inline-block h-2 w-2 animate-bounce bg-muted-foreground [animation-delay:300ms]" />
    </div>
  )
}

function FeedbackButtons({
  feedback,
  onFeedbackChange,
}: {
  messageId: string
  feedback?: "up" | "down"
  onFeedbackChange: (feedback: "up" | "down" | null) => void
}) {
  return (
    <div className="flex items-center gap-1 mt-2.5">
      <button
        aria-label="Thumbs up"
        data-active={feedback === "up" ? "true" : undefined}
        onClick={() => onFeedbackChange(feedback === "up" ? null : "up")}
        className={cn(
          "grid size-6 place-items-center transition-colors",
          feedback === "up"
            ? "text-[var(--slm-accent)]"
            : "text-muted-foreground hover:text-foreground",
        )}
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M14 9V5a3 3 0 0 0-6 0v4M5 11h4l-1 9h8l-1-9h4l-5-7h-4l-5 7z" /></svg>
      </button>
      <button
        aria-label="Thumbs down"
        data-active={feedback === "down" ? "true" : undefined}
        onClick={() => onFeedbackChange(feedback === "down" ? null : "down")}
        className={cn(
          "grid size-6 place-items-center transition-colors",
          feedback === "down"
            ? "text-destructive"
            : "text-muted-foreground hover:text-foreground",
        )}
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M10 15v4a3 3 0 0 0 6 0v-4m5-2h-4l1-9H10l1 9H7l5 7h4l5-7z" /></svg>
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
    <div className="text-[13.5px] leading-[1.7]">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || "")
            const codeString = String(children).replace(/\n$/, "")

            if (match) {
              return <CodeBlockClient code={codeString} language={match[1]} />
            }

            const isBlock =
              className !== undefined || codeString.includes("\n")

            if (isBlock) {
              return <CodeBlockClient code={codeString} language="text" />
            }

            return (
              <code className="bg-muted px-1.5 py-0.5 text-xs text-foreground" {...props}>
                {children}
              </code>
            )
          },
          pre({ children }) {
            return <>{children}</>
          },
          a({ href, children, ...props }) {
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="slm-accent underline underline-offset-2"
                {...props}
              >
                {children}
              </a>
            )
          },
          ul({ children, ...props }) {
            return (
              <ul className="my-2 ml-5 list-disc space-y-1" {...props}>
                {children}
              </ul>
            )
          },
          ol({ children, ...props }) {
            return (
              <ol className="my-2 ml-5 list-decimal space-y-1" {...props}>
                {children}
              </ol>
            )
          },
          strong({ children, ...props }) {
            return <strong className="text-foreground font-semibold" {...props}>{children}</strong>
          },
          p({ children, ...props }) {
            return <p className="mb-2.5 last:mb-0" {...props}>{children}</p>
          },
          li({ children, ...props }) {
            return <li className="my-1" {...props}>{children}</li>
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
        }}
      >
        {content}
      </ReactMarkdown>
      {isStreaming && (
        <span className="cursor-blink ml-0.5" />
      )}
    </div>
  )
}

function UserAvatar() {
  const { data: session } = useSession()
  const image = session?.user?.image
  if (image) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={image} alt="" width={28} height={28} className="rounded-full" />
  }
  return (
    <div className="grid size-7 place-items-center bg-muted text-[10px] font-bold text-muted-foreground rounded-full">
      U
    </div>
  )
}

function SealevelAvatar() {
  // eslint-disable-next-line @next/next/no-img-element
  return <img src="/sealevel.png" alt="Sealevel" width={28} height={28} />
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
      className="grid gap-4"
      style={{ gridTemplateColumns: "32px 1fr" }}
    >
      <div className="pt-0.5">
        {isUser ? <UserAvatar /> : <SealevelAvatar />}
      </div>
      <div className={isUser ? "text-muted-foreground" : ""}>
        <MessageContent
          content={message.content}
          isStreaming={message.isStreaming}
        />
        {!isUser && !message.isStreaming && message.content && (
          <div className="flex items-center gap-2">
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
