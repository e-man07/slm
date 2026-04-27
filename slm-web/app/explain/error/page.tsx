"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { useSession } from "next-auth/react"
import { PageLayout } from "@/components/shared/page-layout"
import { ErrorCodeInput } from "@/components/explain/error-code-input"
import { ErrorResult } from "@/components/explain/error-result"
import { useStreaming } from "@/hooks/use-streaming"
import { decodeError } from "@/lib/api-client"
import type { LookupResult } from "@/lib/sse"
import { cleanModelResponse, fixAnchorCode } from "@/lib/constants"

export default function ExplainErrorPage() {
  const router = useRouter()
  const { status } = useSession()

  React.useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/sign-in?callbackUrl=/explain/error")
    }
  }, [status, router])

  const [lookupResult, setLookupResult] = React.useState<LookupResult | null>(null)
  const [explanation, setExplanation] = React.useState("")
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [notFound, setNotFound] = React.useState(false)
  const explanationRef = React.useRef("")

  const { isStreaming, start } = useStreaming({
    onEvent(event) {
      if (event.type === "lookup") {
        if (event.data) {
          setLookupResult(event.data)
        } else {
          setNotFound(true)
        }
        setIsLoading(false)
      }
      if (event.type === "content") {
        explanationRef.current += event.content
        setExplanation(fixAnchorCode(cleanModelResponse(explanationRef.current)))
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
    async (errorCode: string, programId?: string) => {
      setLookupResult(null)
      setExplanation("")
      explanationRef.current = ""
      setError(null)
      setNotFound(false)
      setIsLoading(true)

      try {
        const response = await decodeError({ errorCode, programId })

        if (!response.ok) {
          const data = await response.json().catch(() => null)
          setError(data?.error?.message ?? `Error: ${response.status}`)
          setIsLoading(false)
          return
        }

        start(response)
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to decode error")
        setIsLoading(false)
      }
    },
    [start],
  )

  return (
    <PageLayout>
      <div className="py-12 space-y-8">
        <div>
          <div className="eyebrow" style={{ color: "var(--slm-accent)" }}>02 / error-decoder</div>
          <h1 className="mt-5 text-4xl font-bold tracking-[-0.025em]">Error Decoder.</h1>
          <p className="mt-2.5 max-w-[56ch] text-sm text-muted-foreground">
            Enter a Solana program error code. We decode it against 41 known programs and explain what went wrong.
          </p>
        </div>

        <ErrorCodeInput onSubmit={handleSubmit} isLoading={isLoading || isStreaming} />

        {error && (
          <div role="alert" className="border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {(lookupResult || explanation || isStreaming || notFound) && (
          <ErrorResult
            lookupResult={lookupResult}
            explanation={explanation}
            isStreaming={isStreaming}
            notFound={notFound}
          />
        )}
      </div>
    </PageLayout>
  )
}
