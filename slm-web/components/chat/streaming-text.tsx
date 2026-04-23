"use client"

import { cn } from "@/lib/utils"
import ReactMarkdown from "react-markdown"

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
    <div className={cn("prose prose-sm prose-invert max-w-none", className)}>
      <ReactMarkdown>{text}</ReactMarkdown>
      {isStreaming && <span className="cursor-blink ml-0.5" />}
    </div>
  )
}
