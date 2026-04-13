"use client"

import { cn } from "@/lib/utils"

interface StreamingTextProps {
  text: string
  isStreaming?: boolean
  className?: string
}

export function StreamingText({
  text,
  isStreaming = false,
  className,
}: StreamingTextProps) {
  return (
    <span className={cn("whitespace-pre-wrap", className)}>
      {text}
      {isStreaming && (
        <span className="ml-0.5 inline-block h-4 w-[2px] animate-pulse bg-foreground" />
      )}
    </span>
  )
}
