"use client"

import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowUp01Icon, StopIcon } from "@hugeicons/core-free-icons"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface ChatInputProps {
  onSend: (message: string) => void
  onStop?: () => void
  isLoading?: boolean
  className?: string
}

export function ChatInput({
  onSend,
  onStop,
  isLoading = false,
  className,
}: ChatInputProps) {
  const [value, setValue] = React.useState("")
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)

  const handleSend = React.useCallback(() => {
    if (!value.trim() || isLoading) return
    onSend(value)
    setValue("")
    // Reset textarea height
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

  // Auto-resize textarea
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
    <div className={cn("border-t border-border bg-background p-4", className)}>
      <div className="mx-auto flex max-w-3xl items-end gap-2">
        <Textarea
          ref={textareaRef}
          value={value}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder="Ask about Solana development..."
          className="min-h-[44px] max-h-[200px] resize-none"
          rows={1}
          disabled={isLoading}
        />
        {isLoading ? (
          <Button
            variant="outline"
            size="icon"
            onClick={onStop}
            aria-label="Stop generating"
          >
            <HugeiconsIcon icon={StopIcon} size={18} />
          </Button>
        ) : (
          <Button
            size="icon"
            onClick={handleSend}
            disabled={!value.trim()}
            aria-label="Send message"
          >
            <HugeiconsIcon icon={ArrowUp01Icon} size={18} />
          </Button>
        )}
      </div>
      <p className="mx-auto mt-2 max-w-3xl text-center text-xs text-muted-foreground">
        <kbd className="rounded border border-border px-1">&#x2318;Enter</kbd> to
        send
      </p>
    </div>
  )
}
