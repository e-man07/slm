"use client"

import * as React from "react"
import { cn } from "@/lib/utils"

interface ChatInputProps {
  onSend: (message: string) => void
  onStop?: () => void
  isLoading?: boolean
  ragEnabled?: boolean
  onRagToggle?: () => void
  className?: string
}

export function ChatInput({
  onSend,
  onStop,
  isLoading = false,
  ragEnabled = true,
  onRagToggle,
  className,
}: ChatInputProps) {
  const [value, setValue] = React.useState("")
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)

  const handleSend = React.useCallback(() => {
    if (!value.trim() || isLoading) return
    onSend(value)
    setValue("")
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
    }
  }, [value, isLoading, onSend])

  const handleKeyDown = React.useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend],
  )

  const handleInput = React.useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      setValue(e.target.value)
      const el = e.target
      el.style.height = "auto"
      el.style.height = Math.min(el.scrollHeight, 200) + "px"
    },
    [],
  )

  return (
    <div className={cn("border-t border-border bg-background px-7 pt-4 pb-6", className)}>
      <div className="mx-auto max-w-[760px]">
        <div
          className="border bg-card transition-colors focus-within:border-[var(--slm-accent)]"
          style={{ borderColor: "var(--slm-border-strong)" }}
        >
          <textarea
            ref={textareaRef}
            value={value}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder="Ask about Solana development\u2026"
            className="block w-full min-h-[52px] max-h-[200px] resize-none border-0 bg-transparent px-4 py-3.5 text-[13.5px] leading-relaxed outline-none placeholder:text-muted-foreground"
            rows={1}
            disabled={isLoading}
          />
          <div className="flex items-center justify-between border-t border-border px-3 py-2">
            <div className="flex gap-0.5">
              <button className="inline-flex items-center gap-1.5 px-2 py-1 text-[11px] text-muted-foreground transition-colors hover:text-foreground">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 11L12 20a5 5 0 0 1-7-7l9-9a3.5 3.5 0 0 1 5 5l-9 9a2 2 0 0 1-3-3l8-8" /></svg>
                attach
              </button>
              <button className="inline-flex items-center gap-1.5 px-2 py-1 text-[11px] text-muted-foreground transition-colors hover:text-foreground">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="4" /></svg>
                slm-7b
              </button>
              <button
                onClick={onRagToggle}
                className={cn(
                  "inline-flex items-center gap-1.5 px-2 py-1 text-[11px] transition-colors hover:text-foreground",
                  ragEnabled ? "text-muted-foreground" : "text-muted-foreground/50",
                )}
              >
                rag &middot; {ragEnabled ? "on" : "off"}
              </button>
            </div>
            {isLoading ? (
              <button
                onClick={onStop}
                className="inline-flex items-center gap-2 px-3 py-1.5 text-[11px] font-semibold tracking-[0.04em] text-muted-foreground border border-border transition-colors hover:text-foreground"
                aria-label="Stop generating"
              >
                STOP <span>&times;</span>
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!value.trim()}
                className="inline-flex items-center gap-2 px-3 py-1.5 text-[11px] font-semibold tracking-[0.04em] transition-colors disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground"
                style={{
                  background: value.trim() ? "var(--slm-accent)" : undefined,
                  color: value.trim() ? "oklch(0.153 0.006 107.1)" : undefined,
                }}
                aria-label="Send message"
              >
                SEND <span>&crarr;</span>
              </button>
            )}
          </div>
        </div>
        <div className="mt-2 flex justify-between text-[10px] text-muted-foreground">
          <span><span className="kbd">&thinsp;&#x2318;&crarr;&thinsp;</span> to send &middot; <span className="kbd">&thinsp;&#x21E7;&crarr;&thinsp;</span> for new line</span>
          <span>Model may hallucinate. Verify critical code.</span>
        </div>
      </div>
    </div>
  )
}
