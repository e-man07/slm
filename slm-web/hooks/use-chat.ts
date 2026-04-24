"use client"

import * as React from "react"
import { chatCompletions } from "@/lib/api-client"
import { cleanModelResponse, fixAnchorCode } from "@/lib/constants"
import { useStreaming } from "./use-streaming"

export interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: number
  isStreaming?: boolean
  feedback?: "up" | "down"
}

interface UseChatOptions {
  apiKey?: string
  /** Existing session id to load. If omitted, a new session is created on first send. */
  sessionId?: string
  /** If true, persist messages to DB via /api/sessions. Requires authed user. */
  persist?: boolean
  /** If false, skip RAG context enrichment. Defaults to true. */
  ragEnabled?: boolean
}

interface UseChatReturn {
  messages: ChatMessage[]
  isLoading: boolean
  error: string | null
  sessionId: string | null
  sendMessage: (content: string) => Promise<void>
  clearChat: () => void
  stopStreaming: () => void
  loadSession: (id: string) => Promise<void>
}

function generateId() {
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

async function persistMessage(
  sessionId: string,
  role: "user" | "assistant",
  content: string,
): Promise<void> {
  try {
    await fetch(`/api/sessions/${sessionId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role, content }),
    })
  } catch {
    // Non-fatal — chat continues to work without persistence
  }
}

async function createSession(title: string): Promise<string | null> {
  try {
    const resp = await fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    })
    if (!resp.ok) return null
    const data = (await resp.json()) as { session: { id: string } }
    return data.session.id
  } catch {
    return null
  }
}

export function useChat(options: UseChatOptions = {}): UseChatReturn {
  const [messages, setMessages] = React.useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [sessionId, setSessionId] = React.useState<string | null>(options.sessionId ?? null)

  const assistantContentRef = React.useRef("")
  const assistantIdRef = React.useRef("")
  const currentSessionIdRef = React.useRef<string | null>(options.sessionId ?? null)

  const { isStreaming, start, stop, createSignal } = useStreaming({
    onEvent(event) {
      if (event.type === "chat_delta") {
        assistantContentRef.current += event.content
        const cleaned = fixAnchorCode(cleanModelResponse(assistantContentRef.current))
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantIdRef.current
              ? { ...msg, content: cleaned }
              : msg,
          ),
        )
      }
    },
    onDone() {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantIdRef.current
            ? { ...msg, isStreaming: false }
            : msg,
        ),
      )
      setIsLoading(false)

      // Persist assistant response once streaming completes
      if (options.persist && currentSessionIdRef.current && assistantContentRef.current) {
        void persistMessage(
          currentSessionIdRef.current,
          "assistant",
          assistantContentRef.current,
        )
      }
    },
    onError(message) {
      setError(message)
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantIdRef.current
            ? { ...msg, isStreaming: false, content: msg.content || "An error occurred." }
            : msg,
        ),
      )
      setIsLoading(false)
    },
  })

  const loadSession = React.useCallback(async (id: string) => {
    const resp = await fetch(`/api/sessions/${id}`)
    if (!resp.ok) {
      setError("Session not found")
      return
    }
    const data = (await resp.json()) as {
      session: {
        id: string
        messages: Array<{ id: string; role: string; content: string; createdAt: string }>
      }
    }
    setSessionId(data.session.id)
    currentSessionIdRef.current = data.session.id
    setMessages(
      data.session.messages
        .filter((m) => m.role === "user" || m.role === "assistant")
        .map((m) => ({
          id: m.id,
          role: m.role as "user" | "assistant",
          content: m.content,
          timestamp: new Date(m.createdAt).getTime(),
        })),
    )
    setError(null)
  }, [])

  const sendMessage = React.useCallback(
    async (content: string) => {
      if (!content.trim() || isLoading) return

      setError(null)
      setIsLoading(true)

      const trimmed = content.trim()

      // Ensure session exists if persisting
      let activeSessionId = currentSessionIdRef.current
      if (options.persist && !activeSessionId) {
        activeSessionId = await createSession(trimmed.slice(0, 60))
        if (activeSessionId) {
          currentSessionIdRef.current = activeSessionId
          setSessionId(activeSessionId)
        }
      }

      const userMessage: ChatMessage = {
        id: generateId(),
        role: "user",
        content: trimmed,
        timestamp: Date.now(),
      }

      const assistantId = generateId()
      assistantIdRef.current = assistantId
      assistantContentRef.current = ""

      const assistantMessage: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        timestamp: Date.now(),
        isStreaming: true,
      }

      setMessages((prev) => [...prev, userMessage, assistantMessage])

      // Persist user message (fire-and-forget)
      if (options.persist && activeSessionId) {
        void persistMessage(activeSessionId, "user", trimmed)
      }

      // Build message history for API
      const apiMessages = [...messages, userMessage].map((msg) => ({
        role: msg.role as "user" | "assistant",
        content: msg.content,
      }))

      try {
        const signal = createSignal()
        const response = await chatCompletions({
          messages: apiMessages,
          stream: true,
          apiKey: options.apiKey,
          signal,
          useRag: options.ragEnabled ?? true,
        })

        if (!response.ok) {
          const errorData = await response.json().catch(() => null)
          const errorMsg =
            errorData?.error?.message ?? `Server error: ${response.status}`
          setError(errorMsg)
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId
                ? { ...msg, isStreaming: false, content: errorMsg }
                : msg,
            ),
          )
          setIsLoading(false)
          return
        }

        start(response)
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to send message"
        setError(message)
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantId
              ? { ...msg, isStreaming: false, content: "Failed to connect to the model." }
              : msg,
          ),
        )
        setIsLoading(false)
      }
    },
    [messages, isLoading, start, createSignal, options.apiKey, options.persist, options.ragEnabled],
  )

  const clearChat = React.useCallback(() => {
    stop()
    setMessages([])
    setError(null)
    setIsLoading(false)
    setSessionId(null)
    currentSessionIdRef.current = null
  }, [stop])

  return {
    messages,
    isLoading: isLoading || isStreaming,
    error,
    sessionId,
    sendMessage,
    clearChat,
    stopStreaming: stop,
    loadSession,
  }
}
