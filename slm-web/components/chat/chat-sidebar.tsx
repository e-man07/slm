"use client"

import * as React from "react"
import { useSession } from "next-auth/react"
import { cn } from "@/lib/utils"
import { RATE_LIMITS } from "@/lib/constants"
import { type SessionItem } from "@/hooks/use-sessions"

function useSidebarUsage(isAuthenticated: boolean) {
  const [data, setData] = React.useState<{ requests: number; tokens: number } | null>(null)

  React.useEffect(() => {
    if (!isAuthenticated) return
    const fetchUsage = () => {
      fetch("/api/usage")
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => setData(d?.today ?? null))
        .catch(() => setData(null))
    }
    fetchUsage()
    const interval = setInterval(fetchUsage, 30_000) // refresh every 30s
    return () => clearInterval(interval)
  }, [isAuthenticated])

  return data
}

function relativeTime(dateStr: string): string {
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const seconds = Math.floor((now - then) / 1000)

  if (seconds < 60) return "now"
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h`
  const days = Math.floor(hours / 24)
  if (days === 1) return "yst"
  if (days < 30) return `${days}d`
  const months = Math.floor(days / 30)
  return `${months}mo`
}

const SIDEBAR_KEY = "slm-sidebar-open-v2"
const SIDEBAR_WIDTH = 260

interface ChatSidebarProps {
  sessions: SessionItem[]
  isLoading: boolean
  activeSessionId: string | null
  onSelectSession: (id: string) => void
  onNewChat: () => void
  onDeleteSession: (id: string) => void
}

export function useSidebarState() {
  // Lazy initializer reads localStorage before first render to avoid the
  // open→closed flash for returning users who explicitly closed the sidebar.
  const [isOpen, setIsOpen] = React.useState(() => {
    if (typeof window === "undefined") return true
    try {
      return localStorage.getItem(SIDEBAR_KEY) !== "false"
    } catch {
      return true
    }
  })

  const toggle = React.useCallback(() => {
    setIsOpen((prev) => {
      const next = !prev
      try { localStorage.setItem(SIDEBAR_KEY, String(next)) } catch { /* ignore */ }
      return next
    })
  }, [])

  const close = React.useCallback(() => {
    setIsOpen(false)
    try { localStorage.setItem(SIDEBAR_KEY, "false") } catch { /* ignore */ }
  }, [])

  return { isOpen, toggle, close, width: SIDEBAR_WIDTH }
}

export function ChatSidebar({
  sessions,
  isLoading,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  isOpen,
  onClose,
}: ChatSidebarProps & { isOpen: boolean; onToggle: () => void; onClose: () => void }) {
  const { data: authSession, status: authStatus } = useSession()
  const isAuthenticated = authStatus === "authenticated" && !!authSession?.user
  const usage = useSidebarUsage(isAuthenticated)
  const tierLimits = RATE_LIMITS.free

  return (
    <>
      {/* Backdrop — mobile */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 md:hidden"
          onClick={onClose}
          aria-hidden
        />
      )}

      {/* Sidebar panel */}
      <aside
        className={cn(
          "fixed left-0 top-14 z-40 flex h-[calc(100svh-3.5rem)] flex-col border-r border-border bg-background transition-transform duration-200 ease-in-out",
          isOpen ? "translate-x-0" : "-translate-x-full",
        )}
        style={{ width: SIDEBAR_WIDTH }}
      >
        {/* Sidebar header with collapse button */}
        <div className="flex h-12 items-center justify-between border-b border-border px-4">
          <span className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Chat History</span>
          <button
            onClick={onClose}
            className="grid size-7 place-items-center text-muted-foreground transition-colors hover:text-foreground hover:bg-muted"
            aria-label="Close sidebar"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M15 4l-8 8 8 8" />
            </svg>
          </button>
        </div>

        <div className="flex flex-1 flex-col gap-7 overflow-y-auto p-5">
          {/* New chat button */}
          <button
            onClick={() => { onNewChat(); if (window.innerWidth < 768) onClose() }}
            className="flex items-center gap-2 border border-border px-3 py-2 text-xs text-muted-foreground transition-colors hover:text-foreground hover:bg-muted"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 5v14M5 12h14" /></svg>
            New chat
          </button>

          {/* Recent sessions */}
          <div>
            <div className="flex justify-between text-[10px] uppercase tracking-[0.14em] text-muted-foreground mb-2.5">
              <span>Recent</span>
              <span style={{ color: "var(--slm-border-strong)" }}>{sessions.length}</span>
            </div>

            {!isAuthenticated ? (
              <p className="py-4 text-xs text-muted-foreground text-center">Sign in to save chats</p>
            ) : isLoading && sessions.length === 0 ? (
              <div className="space-y-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="h-8 animate-pulse bg-muted/50" />
                ))}
              </div>
            ) : sessions.length === 0 ? (
              <p className="py-4 text-xs text-muted-foreground text-center">No chats yet</p>
            ) : (
              sessions.map((s) => (
                <div
                  key={s.id}
                  className={cn(
                    "group flex w-full items-center gap-2.5 py-2 px-2.5 -mx-2.5 text-[12.5px] border-l-2 border-transparent transition-all cursor-pointer",
                    s.id === activeSessionId
                      ? "text-foreground border-l-[var(--slm-accent)]"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted",
                  )}
                >
                  <button
                    onClick={() => {
                      onSelectSession(s.id)
                      if (window.innerWidth < 768) onClose()
                    }}
                    className="flex flex-1 items-center gap-2.5 min-w-0 text-left"
                  >
                    <span>{s.id === activeSessionId ? "\u25CF" : "\u00b7"}</span>
                    <span className="truncate flex-1">{s.title || "New chat"}</span>
                    <span className="shrink-0 text-[10px]" style={{ color: "var(--slm-border-strong)" }}>
                      {relativeTime(s.updatedAt)}
                    </span>
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); onDeleteSession(s.id) }}
                    className="shrink-0 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-opacity"
                    aria-label="Delete chat"
                  >
                    &times;
                  </button>
                </div>
              ))
            )}
          </div>

          {/* Usage — at bottom */}
          {isAuthenticated && (
            <div className="mt-auto">
              <div className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground mb-2.5">Usage</div>
              {(() => {
                const tokens = usage?.tokens ?? 0
                const exceeded = tokens > tierLimits.tokensPerDay
                return (
                  <div className="text-[11px] text-muted-foreground leading-[1.8]">
                    <div className="flex justify-between">
                      <span>Requests today</span>
                      <span className="mono-num">{usage?.requests ?? 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Tokens today</span>
                      <span className="mono-num" style={exceeded ? { color: "var(--destructive, #ef4444)" } : undefined}>{tokens.toLocaleString()}</span>
                    </div>
                    <div className="relative my-1.5 h-0.5 bg-muted">
                      <div
                        className="absolute inset-y-0 left-0"
                        style={{
                          background: exceeded ? "var(--destructive, #ef4444)" : "var(--slm-accent)",
                          width: `${Math.min((tokens / tierLimits.tokensPerDay) * 100, 100)}%`,
                        }}
                      />
                    </div>
                    <div className="flex justify-between" style={{ fontSize: 10, opacity: 0.6 }}>
                      <span>Limit</span>
                      <span className="mono-num">{(tierLimits.tokensPerDay / 1000).toFixed(0)}K tokens/day</span>
                    </div>
                  </div>
                )
              })()}
            </div>
          )}
        </div>
      </aside>
    </>
  )
}
