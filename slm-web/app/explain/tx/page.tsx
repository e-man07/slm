"use client"

import * as React from "react"
import { PageLayout } from "@/components/shared/page-layout"
import { TxSignatureInput } from "@/components/explain/tx-signature-input"
import { TxResult } from "@/components/explain/tx-result"
import { Skeleton } from "@/components/ui/skeleton"
import { useStreaming } from "@/hooks/use-streaming"
import { explainTransaction } from "@/lib/api-client"
import type { TxData } from "@/lib/sse"

export default function ExplainTxPage() {
  const [txData, setTxData] = React.useState<TxData | null>(null)
  const [explanation, setExplanation] = React.useState("")
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const explanationRef = React.useRef("")

  const { isStreaming, start } = useStreaming({
    onEvent(event) {
      if (event.type === "tx_data") {
        setTxData(event.data)
        setIsLoading(false)
      }
      if (event.type === "content") {
        explanationRef.current += event.content
        setExplanation(explanationRef.current)
      }
    },
    onDone() {
      setIsLoading(false)
    },
    onError(message) {
      setError(message)
      setIsLoading(false)
    },
  })

  const handleSubmit = React.useCallback(
    async (signature: string) => {
      setTxData(null)
      setExplanation("")
      explanationRef.current = ""
      setError(null)
      setIsLoading(true)

      try {
        const response = await explainTransaction({ signature })

        if (!response.ok) {
          const data = await response.json().catch(() => null)
          setError(data?.error?.message ?? `Error: ${response.status}`)
          setIsLoading(false)
          return
        }

        start(response)
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch transaction")
        setIsLoading(false)
      }
    },
    [start],
  )

  return (
    <PageLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Transaction Explainer</h1>
          <p className="mt-1 text-muted-foreground">
            Paste a Solana transaction signature to get a human-readable explanation
          </p>
        </div>

        <TxSignatureInput onSubmit={handleSubmit} isLoading={isLoading || isStreaming} />

        {error && (
          <div className="border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {isLoading && !txData && (
          <div className="space-y-3">
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        )}

        {(txData || explanation || isStreaming) && (
          <TxResult txData={txData} explanation={explanation} isStreaming={isStreaming} />
        )}
      </div>
    </PageLayout>
  )
}
