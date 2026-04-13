"use client"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { StreamingText } from "@/components/chat/streaming-text"
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
    <div className="space-y-4">
      {lookupResult && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Error Details</CardTitle>
              <Badge variant="destructive">{lookupResult.hex}</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div>
              <span className="text-muted-foreground">Program</span>
              <p className="font-medium">{lookupResult.program_name}</p>
            </div>
            <div>
              <span className="text-muted-foreground">Error</span>
              <p className="font-medium">{lookupResult.error_name}</p>
            </div>
            <div>
              <span className="text-muted-foreground">Message</span>
              <p>{lookupResult.error_message}</p>
            </div>
            <div>
              <span className="text-muted-foreground">Code</span>
              <p className="font-mono text-xs">
                {lookupResult.hex} (decimal: {lookupResult.code})
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {notFound && !lookupResult && (
        <Card>
          <CardContent className="py-4 text-sm text-muted-foreground">
            Error not found in 41 known Solana programs. The AI will attempt to
            explain based on the error code pattern.
          </CardContent>
        </Card>
      )}

      {(explanation || isStreaming) && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">AI Explanation</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm leading-relaxed">
              <StreamingText text={explanation} isStreaming={isStreaming} />
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
