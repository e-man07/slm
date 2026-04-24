"use client"

import * as React from "react"
import { useSearchParams, useRouter } from "next/navigation"
import { useSession } from "next-auth/react"
import { NavBar } from "@/components/nav-bar"
import { ChatMessage } from "@/components/chat/chat-message"
import { ChatInput } from "@/components/chat/chat-input"
import { ChatSidebar, useSidebarState } from "@/components/chat/chat-sidebar"
import { useChat } from "@/hooks/use-chat"
import { useSessions } from "@/hooks/use-sessions"
// SUGGESTED_PROMPTS used via PROMPT_GRID below

const PROMPT_GRID = [
  { cat: "PDA", text: "How do I derive a PDA in Anchor?" },
  { cat: "SPL TOKEN", text: "Write a token transfer in Anchor 0.30+" },
  { cat: "CPI", text: "Explain this CPI call structure" },
  { cat: "SCAFFOLD", text: "Scaffold an escrow program" },
]

function ChatPageInner() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const { data: authSession, status } = useSession()
  const isAuthenticated = !!authSession?.user

  // Redirect unauthenticated users to sign-in
  React.useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/sign-in?callbackUrl=/chat")
    }
  }, [status, router])
  const sidebar = useSidebarState()
  const [ragEnabled, setRagEnabled] = React.useState(true)

  const {
    messages,
    isLoading,
    error,
    sessionId,
    sendMessage,
    clearChat,
    stopStreaming,
    loadSession,
  } = useChat({ persist: isAuthenticated, ragEnabled })

  const { sessions, isLoading: sessionsLoading, refresh, deleteSession } =
    useSessions()

  const scrollRef = React.useRef<HTMLDivElement>(null)
  const hasAutoSent = React.useRef(false)
  const prevSessionId = React.useRef<string | null>(null)

  React.useEffect(() => {
    const prompt = searchParams.get("prompt")
    if (prompt && !hasAutoSent.current) {
      hasAutoSent.current = true
      sendMessage(decodeURIComponent(prompt))
    }
  }, [searchParams, sendMessage])

  React.useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  React.useEffect(() => {
    if (sessionId && prevSessionId.current !== sessionId) {
      prevSessionId.current = sessionId
      void refresh()
    }
  }, [sessionId, refresh])

  const handleSelectSession = React.useCallback(
    async (id: string) => {
      await loadSession(id)
    },
    [loadSession],
  )

  const handleNewChat = React.useCallback(() => {
    clearChat()
  }, [clearChat])

  const handleDeleteSession = React.useCallback(
    async (id: string) => {
      if (id === sessionId) {
        clearChat()
      }
      await deleteSession(id)
    },
    [sessionId, clearChat, deleteSession],
  )

  const isEmpty = messages.length === 0

  return (
    <div className="flex h-svh flex-col">
      <NavBar minimal />

      <div className="relative flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <ChatSidebar
          sessions={sessions}
          isLoading={sessionsLoading}
          activeSessionId={sessionId}
          onSelectSession={handleSelectSession}
          onNewChat={handleNewChat}
          onDeleteSession={handleDeleteSession}
          isOpen={sidebar.isOpen}
          onToggle={sidebar.toggle}
          onClose={sidebar.close}
        />

        {/* Main chat area — shifts right when sidebar is open */}
        <section
          className="flex flex-1 flex-col min-h-0 min-w-0 transition-[margin] duration-200 ease-in-out"
          style={{ marginLeft: sidebar.isOpen ? sidebar.width : 0 }}
        >
          {/* Chat top bar — always show hamburger, full bar only when messages exist */}
          <div
            className="flex h-12 items-center justify-between border-b border-border px-4"
          >
            <div className="flex items-center gap-3">
              {!sidebar.isOpen && (
                <button
                  onClick={sidebar.toggle}
                  className="grid size-8 place-items-center text-muted-foreground transition-colors hover:text-foreground hover:bg-muted"
                  aria-label="Open sidebar"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                    <path d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                </button>
              )}
              {!isEmpty && <span className="text-[13px] font-semibold">Sealevel</span>}
            </div>
            {!isEmpty && (
              <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                <span className="inline-flex items-center gap-1.5 border border-border px-2.5 py-1">
                  <span className="inline-block size-1.5" style={{ background: "var(--slm-accent)" }} />
                  live
                </span>
              </div>
            )}
          </div>

          {/* Messages area */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-8">
            {isEmpty ? (
              <div className="flex h-full items-center justify-center px-10">
                <div className="max-w-[720px] w-full">
                  <div className="text-[11px] tracking-[0.14em] slm-accent mb-3">
                    SEALEVEL / READY / TYPE TO START
                  </div>
                  <h2 className="text-[40px] font-bold tracking-[-0.02em] leading-[1.1] max-w-[16ch]">
                    Ask anything about{" "}
                    <span className="text-muted-foreground">Solana &amp; Anchor</span>.
                  </h2>
                  <p className="mt-3 text-[13px] text-muted-foreground">
                    Uses the model fine-tuned on 270K Solana records. Streams responses, cites docs, suggests fixes.{" "}
                    <span className="kbd">&thinsp;&#x2318;K&thinsp;</span> to focus.
                  </p>
                  <div className="mt-8 grid grid-cols-1 border-l border-t border-border sm:grid-cols-2">
                    {PROMPT_GRID.map((p) => (
                      <button
                        key={p.text}
                        onClick={() => sendMessage(p.text)}
                        className="group flex items-center justify-between gap-3 border-b border-r border-border p-4 text-left transition-colors hover:bg-muted"
                      >
                        <div>
                          <div className="text-[10px] tracking-[0.12em] text-muted-foreground">{p.cat}</div>
                          <div className="mt-1 text-[13px]">{p.text}</div>
                        </div>
                        <span className="text-muted-foreground transition-all group-hover:translate-x-0.5 group-hover:text-[var(--slm-accent)]">&rarr;</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="mx-auto flex max-w-[760px] flex-col gap-8">
                {messages.map((message) => (
                  <ChatMessage
                    key={message.id}
                    message={message}
                    onFeedback={(_, feedback) => {
                      if (!feedback || message.role !== "assistant" || !message.content) return
                      fetch("/api/feedback", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                          responsePrefix: message.content.slice(0, 100),
                          signal: feedback,
                        }),
                      }).catch(() => {})
                    }}
                  />
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
            ragEnabled={ragEnabled}
            onRagToggle={() => setRagEnabled((v) => !v)}
          />
        </section>
      </div>
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
