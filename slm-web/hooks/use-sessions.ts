"use client"

import * as React from "react"

export interface SessionItem {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  _count: { messages: number }
}

interface UseSessionsReturn {
  sessions: SessionItem[]
  isLoading: boolean
  refresh: () => Promise<void>
  deleteSession: (id: string) => Promise<void>
}

export function useSessions(): UseSessionsReturn {
  const [sessions, setSessions] = React.useState<SessionItem[]>([])
  const [isLoading, setIsLoading] = React.useState(false)

  const refresh = React.useCallback(async () => {
    setIsLoading(true)
    try {
      const resp = await fetch("/api/sessions?source=web")
      if (!resp.ok) {
        setSessions([])
        return
      }
      const data = (await resp.json()) as { sessions: SessionItem[] }
      setSessions(data.sessions)
    } catch {
      setSessions([])
    } finally {
      setIsLoading(false)
    }
  }, [])

  const deleteSession = React.useCallback(
    async (id: string) => {
      // Optimistic removal
      setSessions((prev) => prev.filter((s) => s.id !== id))
      try {
        await fetch(`/api/sessions/${id}`, { method: "DELETE" })
      } catch {
        // Re-fetch on failure
        await refresh()
      }
    },
    [refresh],
  )

  // Fetch on mount
  React.useEffect(() => {
    void refresh()
  }, [refresh])

  return { sessions, isLoading, refresh, deleteSession }
}
