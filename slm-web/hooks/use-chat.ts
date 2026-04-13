"use client"

import * as React from "react"
import { chatCompletions } from "@/lib/api-client"
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
}

interface UseChatReturn {
  messages: ChatMessage[]
  isLoading: boolean
  error: string | null
  sendMessage: (content: string) => Promise<void>
  clearChat: () => void
  stopStreaming: () => void
}

function generateId() {
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export function useChat(options: UseChatOptions = {}): UseChatReturn {
  const [messages, setMessages] = React.useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const assistantContentRef = React.useRef("")
  const assistantIdRef = React.useRef("")

  const { isStreaming, start, stop } = useStreaming({
    onEvent(event) {
      if (event.type === "chat_delta") {
        assistantContentRef.current += event.content
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantIdRef.current
              ? { ...msg, content: assistantContentRef.current }
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

  const sendMessage = React.useCallback(
    async (content: string) => {
      if (!content.trim() || isLoading) return

      setError(null)
      setIsLoading(true)

      const userMessage: ChatMessage = {
        id: generateId(),
        role: "user",
        content: content.trim(),
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

      // Build message history for API
      const apiMessages = [...messages, userMessage].map((msg) => ({
        role: msg.role as "user" | "assistant",
        content: msg.content,
      }))

      try {
        const response = await chatCompletions({
          messages: apiMessages,
          stream: true,
          apiKey: options.apiKey,
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
    [messages, isLoading, start],
  )

  const clearChat = React.useCallback(() => {
    stop()
    setMessages([])
    setError(null)
    setIsLoading(false)
  }, [stop])

  return {
    messages,
    isLoading: isLoading || isStreaming,
    error,
    sendMessage,
    clearChat,
    stopStreaming: stop,
  }
}
