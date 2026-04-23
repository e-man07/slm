"use client"

import { MarkdownContent } from "@/components/shared/markdown-content"
import type { LookupResult } from "@/lib/sse"

interface ErrorResultProps {
  lookupResult: LookupResult | null
  explanation: string
  isStreaming: boolean
  notFound?: boolean
}

export function ErrorResult({
  lookupResult,
  explanation,
  isStreaming,
  notFound = false,
}: ErrorResultProps) {
  return (
    <div className="space-y-6">
      {lookupResult && (
        <div className="border border-border">
          <div className="flex items-center justify-between border-b border-border px-5 py-3">
            <span className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Error Details</span>
            <span
              className="px-2 py-0.5 text-[10px] font-semibold tracking-[0.14em] border"
              style={{ color: "var(--destructive)", borderColor: "var(--destructive)" }}
            >
              {lookupResult.hex}
            </span>
          </div>
          <div className="p-5">
            <div className="space-y-0">
              <div className="flex justify-between items-baseline py-2.5 border-b border-dashed border-border text-xs">
                <span className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">Program</span>
                <span className="font-medium">{lookupResult.program_name}</span>
              </div>
              <div className="flex justify-between items-baseline py-2.5 border-b border-dashed border-border text-xs">
                <span className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">Error</span>
                <span className="font-medium">{lookupResult.error_name}</span>
              </div>
              <div className="flex justify-between items-baseline py-2.5 border-b border-dashed border-border text-xs">
                <span className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">Message</span>
                <span className="text-muted-foreground">{lookupResult.error_message}</span>
              </div>
              <div className="flex justify-between items-baseline py-2.5 text-xs">
                <span className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">Code</span>
                <span className="mono-num">{lookupResult.hex} (decimal: {lookupResult.code})</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {notFound && !lookupResult && (
        <div className="border border-border px-5 py-4 text-xs text-muted-foreground">
          Error not found in 41 known Solana programs. The AI will attempt to
          explain based on the error code pattern.
        </div>
      )}

      {(explanation || isStreaming) && (
        <div className="border border-border">
          <div className="flex items-center justify-between border-b border-border px-5 py-3">
            <span className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">AI Explanation</span>
            {isStreaming && (
              <span className="flex items-center gap-1.5 text-[10px] slm-accent">
                <span
                  className="inline-block size-1.5"
                  style={{ background: "var(--slm-accent)", animation: "pulse-dot 1s infinite" }}
                />
                streaming
              </span>
            )}
          </div>
          <div className="p-5">
            <MarkdownContent content={explanation} isStreaming={isStreaming} />
          </div>
        </div>
      )}
    </div>
  )
}
