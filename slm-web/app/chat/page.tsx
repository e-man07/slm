"use client"

import * as React from "react"
import { useSearchParams } from "next/navigation"
import { HugeiconsIcon } from "@hugeicons/react"
import { Delete01Icon } from "@hugeicons/core-free-icons"
import { NavBar } from "@/components/nav-bar"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { ChatMessage } from "@/components/chat/chat-message"
import { ChatInput } from "@/components/chat/chat-input"
import { useChat } from "@/hooks/use-chat"
import { SUGGESTED_PROMPTS } from "@/lib/constants"

function ChatPageInner() {
  const searchParams = useSearchParams()
  const { messages, isLoading, error, sendMessage, clearChat, stopStreaming } =
    useChat()
  const scrollRef = React.useRef<HTMLDivElement>(null)
  const hasAutoSent = React.useRef(false)

  // Auto-send prompt from search params (e.g., from docs "Try it" buttons)
  React.useEffect(() => {
    const prompt = searchParams.get("prompt")
    if (prompt && !hasAutoSent.current) {
      hasAutoSent.current = true
      sendMessage(decodeURIComponent(prompt))
    }
  }, [searchParams, sendMessage])

  // Auto-scroll to bottom on new messages
  React.useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const isEmpty = messages.length === 0

  return (
    <div className="flex h-svh flex-col">
      <NavBar minimal />

      {/* Header with clear button */}
      {!isEmpty && (
        <div className="flex items-center justify-end border-b border-border px-4 py-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={clearChat}
            className="text-muted-foreground"
          >
            <HugeiconsIcon icon={Delete01Icon} size={16} />
            New chat
          </Button>
        </div>
      )}

      {/* Messages area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        {isEmpty ? (
          <div className="flex h-full flex-col items-center justify-center gap-8 px-4">
            <div className="text-center">
              <h2 className="text-2xl font-bold">SLM</h2>
              <p className="mt-2 text-muted-foreground">
                Ask anything about Solana & Anchor development
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-2">
              {SUGGESTED_PROMPTS.map((prompt) => (
                <Badge
                  key={prompt}
                  variant="outline"
                  className="cursor-pointer px-3 py-2 text-sm transition-colors hover:bg-accent"
                  onClick={() => sendMessage(prompt)}
                >
                  {prompt}
                </Badge>
              ))}
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-4 px-4 py-6">
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
          </div>
        )}
      </div>

      {/* Error display */}
      {error && (
        <div className="border-t border-destructive/20 bg-destructive/5 px-4 py-2 text-center text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Input area */}
      <ChatInput
        onSend={sendMessage}
        onStop={stopStreaming}
        isLoading={isLoading}
      />
    </div>
  )
}

export default function ChatPage() {
  return (
    <React.Suspense fallback={null}>
      <ChatPageInner />
    </React.Suspense>
  )
}
