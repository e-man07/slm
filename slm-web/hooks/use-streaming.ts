"use client"

import * as React from "react"
import { parseSSEStream, type SSEEvent } from "@/lib/sse"

interface UseStreamingOptions {
  onEvent?: (event: SSEEvent) => void
  onDone?: () => void
  onError?: (error: string) => void
}

interface UseStreamingReturn {
  isStreaming: boolean
  error: string | null
  start: (response: Response) => void
  stop: () => void
  /** Creates a new AbortController and returns its signal. Pass to fetch(). */
  createSignal: () => AbortSignal
}

export function useStreaming(options: UseStreamingOptions = {}): UseStreamingReturn {
  const [isStreaming, setIsStreaming] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const abortRef = React.useRef<AbortController | null>(null)

  const stop = React.useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setIsStreaming(false)
  }, [])

  const createSignal = React.useCallback(() => {
    stop()
    const controller = new AbortController()
    abortRef.current = controller
    return controller.signal
  }, [stop])

  const start = React.useCallback(
    (response: Response) => {
      setError(null)
      setIsStreaming(true)

      // Reuse existing controller (from createSignal) or create a new one
      const controller = abortRef.current ?? new AbortController()
      abortRef.current = controller

      ;(async () => {
        try {
          for await (const event of parseSSEStream(response)) {
            if (controller.signal.aborted) break

            if (event.type === "done") {
              options.onDone?.()
              break
            }

            if (event.type === "error") {
              setError(event.message)
              options.onError?.(event.message)
              break
            }

            options.onEvent?.(event)
          }
        } catch (err) {
          if (!controller.signal.aborted) {
            const message = err instanceof Error ? err.message : "Stream error"
            setError(message)
            options.onError?.(message)
          }
        } finally {
          setIsStreaming(false)
          abortRef.current = null
        }
      })()
    },
    [options],
  )

  React.useEffect(() => {
    return () => stop()
  }, [stop])

  return { isStreaming, error, start, stop, createSignal }
}
