"use client"

import * as React from "react"
import { PageLayout } from "@/components/shared/page-layout"
import { useStreaming } from "@/hooks/use-streaming"
import { explainTransaction } from "@/lib/api-client"
import { MarkdownContent } from "@/components/shared/markdown-content"
import { shortenAddress, formatSolAmount } from "@/lib/helius"
import type { TxData } from "@/lib/sse"
import { cleanModelResponse, fixAnchorCode } from "@/lib/constants"

const EXAMPLE_SIGNATURE =
  "5UfDuX7WXYxjng1PYLJmzGRqaWEd7dMN5Ld5sgsMUPoStSK7F4EzPbf2jnEHrgTCFm1GZeKVgU9LnE2RXm8S8Bu"

function isValidBase58(str: string): boolean {
  return /^[1-9A-HJ-NP-Za-km-z]{87,88}$/.test(str)
}

interface TxInstruction {
  programId?: string
  accounts?: string[]
  data?: string
}

export default function ExplainTxPage() {
  const [value, setValue] = React.useState("")
  const [inputError, setInputError] = React.useState("")
  const [txData, setTxData] = React.useState<TxData | null>(null)
  const [explanation, setExplanation] = React.useState("")
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const explanationRef = React.useRef("")
  const [expandedIx, setExpandedIx] = React.useState<number | null>(null)

  const { isStreaming, start } = useStreaming({
    onEvent(event) {
      if (event.type === "tx_data") {
        setTxData(event.data)
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
    async (signature?: string) => {
      const sig = signature ?? value.trim()
      if (!sig) {
        setInputError("Please enter a transaction signature")
        return
      }
      if (!isValidBase58(sig)) {
        setInputError("Invalid transaction signature format")
        return
      }
      setInputError("")
      setTxData(null)
      setExplanation("")
      explanationRef.current = ""
      setError(null)
      setIsLoading(true)

      try {
        const response = await explainTransaction({ signature: sig })

        if (!response.ok) {
          const data = await response.json().catch(() => null)
          setError(data?.error?.message ?? `Error: ${response.status}`)
          setIsLoading(false)
          return
        }

        start(response)
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to fetch transaction",
        )
        setIsLoading(false)
      }
    },
    [start, value],
  )

  const handlePaste = React.useCallback(async () => {
    const text = await navigator.clipboard.readText()
    setValue(text.trim())
    setInputError("")
  }, [])

  const handleKeyDown = React.useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault()
        handleSubmit()
      }
    },
    [handleSubmit],
  )

  const busy = isLoading || isStreaming

  const instructions = txData
    ? (txData.instructions as TxInstruction[]).filter((ix) => ix.programId)
    : []

  const kvRows = txData
    ? [
        { label: "Slot", value: "---" },
        {
          label: "Block time",
          value: txData.blockTime
            ? new Date(txData.blockTime * 1000).toLocaleString()
            : "---",
        },
        {
          label: "Fee",
          value: `${formatSolAmount(txData.fee * 1e9)} SOL`,
        },
        { label: "Compute", value: "---" },
        {
          label: "Instructions",
          value: String(txData.instructions.length),
        },
        { label: "Signers", value: shortenAddress(txData.feePayer, 6) },
        { label: "Accounts", value: "---" },
      ]
    : []

  return (
    <PageLayout>
      <div style={{ fontFamily: "'JetBrains Mono', monospace" }}>
        {/* ── Header ── */}
        <div className="mb-10 mt-12">
          <p
            className="eyebrow mb-3 text-[11px] uppercase tracking-[0.18em]"
            style={{ color: "oklch(0.65 0.05 130)" }}
          >
            02 / tx-explainer
          </p>
          <h1
            className="text-4xl font-semibold tracking-tight"
            style={{ color: "oklch(0.97 0 0)" }}
          >
            Transaction Explainer.
          </h1>
          <p
            className="mt-2 max-w-xl text-sm leading-relaxed"
            style={{ color: "oklch(0.55 0.02 130)" }}
          >
            Paste a Solana transaction signature to get a human-readable,
            AI-generated explanation of what happened on-chain.
          </p>
        </div>

        {/* ── Input ── */}
        <div
          style={{
            border: "1px solid oklch(0.30 0.02 130)",
            background: "var(--slm-terminal-bg, oklch(0.12 0.01 130))",
          }}
        >
          <div className="flex items-center gap-3 px-5 py-4">
            <span
              className="text-base font-bold select-none"
              style={{ color: "var(--slm-accent, oklch(0.89 0.19 128))" }}
            >
              $
            </span>
            <input
              value={value}
              onChange={(e) => {
                setValue(e.target.value)
                setInputError("")
              }}
              onKeyDown={handleKeyDown}
              placeholder="Paste a Solana transaction signature..."
              disabled={busy}
              className="flex-1 bg-transparent text-sm outline-none placeholder:opacity-30"
              style={{
                color: "oklch(0.85 0.02 130)",
                fontFamily: "inherit",
              }}
            />
            <button
              onClick={() => handleSubmit()}
              disabled={busy || !value.trim()}
              className="px-4 py-1.5 text-xs font-semibold uppercase tracking-wider transition-opacity disabled:opacity-30"
              style={{
                background: "var(--slm-accent, oklch(0.89 0.19 128))",
                color: "oklch(0.13 0.02 130)",
              }}
            >
              {busy ? "..." : "Explain"}
            </button>
          </div>

          {/* Bottom bar */}
          <div
            className="flex items-center justify-between px-5 py-2 text-[10px]"
            style={{
              borderTop: "1px solid oklch(0.22 0.01 130)",
              color: "oklch(0.40 0.02 130)",
            }}
          >
            <span>{value.length} / 88 chars</span>
            <div className="flex items-center gap-4">
              <button
                type="button"
                onClick={() => {
                  setValue(EXAMPLE_SIGNATURE)
                  setInputError("")
                }}
                className="underline-offset-2 hover:underline"
                style={{ color: "oklch(0.55 0.03 130)" }}
              >
                try example
              </button>
              <button
                type="button"
                onClick={handlePaste}
                className="underline-offset-2 hover:underline"
                style={{ color: "oklch(0.55 0.03 130)" }}
              >
                paste
              </button>
              <span
                className="kbd inline-flex items-center gap-1"
                style={{ color: "oklch(0.40 0.02 130)" }}
              >
                <span
                  style={{
                    color: "var(--slm-accent, oklch(0.89 0.19 128))",
                  }}
                >
                  &crarr;
                </span>{" "}
                to submit
              </span>
            </div>
          </div>
        </div>

        {inputError && (
          <p className="mt-2 text-xs" style={{ color: "oklch(0.65 0.20 25)" }}>
            {inputError}
          </p>
        )}

        {/* ── Error ── */}
        {error && (
          <div
            className="mt-4 px-5 py-3 text-xs"
            style={{
              border: "1px solid oklch(0.40 0.18 25)",
              color: "oklch(0.65 0.20 25)",
              background: "oklch(0.65 0.20 25 / 0.06)",
            }}
          >
            {error}
          </div>
        )}

        {/* ── Loading skeleton ── */}
        {isLoading && !txData && (
          <div className="mt-6 space-y-3">
            <div
              className="h-32 w-full animate-pulse"
              style={{ background: "oklch(0.18 0.01 130)" }}
            />
            <div
              className="h-20 w-full animate-pulse"
              style={{ background: "oklch(0.18 0.01 130)" }}
            />
          </div>
        )}

        {/* ── Result split ── */}
        {(txData || explanation || isStreaming) && (
          <div
            className="mt-8 grid"
            style={{
              gridTemplateColumns: "1fr 1.4fr",
              border: "1px solid oklch(0.30 0.02 130)",
            }}
          >
            {/* Left: tx details */}
            <div
              className="p-6"
              style={{ borderRight: "1px solid oklch(0.30 0.02 130)" }}
            >
              {txData && (
                <>
                  {/* Status */}
                  <div className="flex items-center gap-2">
                    <span
                      className="inline-block h-2 w-2"
                      style={{
                        background:
                          txData.status === "success"
                            ? "oklch(0.72 0.19 145)"
                            : "oklch(0.65 0.20 25)",
                        borderRadius: "50%",
                        animation:
                          "pulse 2s cubic-bezier(0.4,0,0.6,1) infinite",
                      }}
                    />
                    <span
                      className="text-xs font-medium"
                      style={{
                        color:
                          txData.status === "success"
                            ? "oklch(0.72 0.19 145)"
                            : "oklch(0.65 0.20 25)",
                      }}
                    >
                      {txData.status === "success" ? "Success" : "Failed"}{" "}
                      &middot; Mainnet
                    </span>
                  </div>

                  {/* Signature */}
                  <p
                    className="mt-3 break-all text-[11px] leading-relaxed"
                    style={{ color: "oklch(0.50 0.02 130)" }}
                  >
                    {txData.feePayer}
                  </p>

                  {/* KV rows */}
                  <div className="mt-5">
                    {kvRows.map((row) => (
                      <div
                        key={row.label}
                        className="flex items-center justify-between py-2.5 text-xs"
                        style={{
                          borderTop: "1px dashed oklch(0.22 0.01 130)",
                        }}
                      >
                        <span style={{ color: "oklch(0.45 0.02 130)" }}>
                          {row.label}
                        </span>
                        <span
                          style={{
                            color: "oklch(0.75 0.02 130)",
                            fontVariantNumeric: "tabular-nums",
                          }}
                        >
                          {row.value}
                        </span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>

            {/* Right: AI explanation */}
            <div className="p-6">
              <div className="flex items-center justify-between">
                <span
                  className="text-[11px] uppercase tracking-[0.14em]"
                  style={{ color: "oklch(0.55 0.04 130)" }}
                >
                  Plain english
                </span>
                {isStreaming && (
                  <div className="flex items-center gap-1.5">
                    <span
                      className="inline-block h-1.5 w-1.5"
                      style={{
                        background: "oklch(0.72 0.19 145)",
                        borderRadius: "50%",
                        animation:
                          "pulse 2s cubic-bezier(0.4,0,0.6,1) infinite",
                      }}
                    />
                    <span
                      className="text-[10px]"
                      style={{ color: "oklch(0.55 0.08 145)" }}
                    >
                      streaming
                    </span>
                  </div>
                )}
              </div>
              <div
                className="mt-4 text-sm leading-relaxed"
                style={{ color: "oklch(0.78 0.02 130)" }}
              >
                <MarkdownContent content={explanation} isStreaming={isStreaming} />
              </div>
            </div>
          </div>
        )}

        {/* ── Instructions list ── */}
        {txData && instructions.length > 0 && (
          <div
            className="mt-6 mb-16"
            style={{
              border: "1px solid oklch(0.25 0.02 130)",
            }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-5 py-3 text-[11px] uppercase tracking-[0.14em]"
              style={{
                color: "oklch(0.55 0.04 130)",
                borderBottom: "1px solid oklch(0.25 0.02 130)",
                background: "oklch(0.12 0.01 130)",
              }}
            >
              <span>
                Instructions &middot; {instructions.length}
              </span>
            </div>

            {/* Rows */}
            {instructions.map((ix, i) => {
              const accounts = ix.accounts ?? []
              const isOpen = expandedIx === i

              return (
                <div key={i}>
                  <button
                    type="button"
                    onClick={() => setExpandedIx(isOpen ? null : i)}
                    className="flex w-full items-center gap-4 px-5 py-3 text-left text-xs transition-colors"
                    style={{
                      borderBottom:
                        i < instructions.length - 1 || isOpen
                          ? "1px solid oklch(0.20 0.01 130)"
                          : "none",
                      color: "oklch(0.70 0.02 130)",
                    }}
                  >
                    <span
                      className="w-6 text-center"
                      style={{
                        color: "oklch(0.40 0.02 130)",
                        fontVariantNumeric: "tabular-nums",
                      }}
                    >
                      {i}
                    </span>
                    <span className="flex-1" style={{ color: "oklch(0.65 0.03 130)" }}>
                      {shortenAddress(ix.programId!)}
                    </span>
                    <span style={{ color: "oklch(0.45 0.02 130)" }}>
                      {accounts.length} account{accounts.length !== 1 ? "s" : ""}
                    </span>
                    <span
                      className="transition-transform"
                      style={{
                        color: "oklch(0.40 0.02 130)",
                        transform: isOpen ? "rotate(90deg)" : "none",
                      }}
                    >
                      &rsaquo;
                    </span>
                  </button>

                  {isOpen && (
                    <div
                      className="space-y-2 px-5 py-4 text-[11px]"
                      style={{
                        background: "oklch(0.11 0.01 130)",
                        borderBottom:
                          i < instructions.length - 1
                            ? "1px solid oklch(0.20 0.01 130)"
                            : "none",
                      }}
                    >
                      <div>
                        <span style={{ color: "oklch(0.40 0.02 130)" }}>
                          Program ID:{" "}
                        </span>
                        <span
                          className="break-all"
                          style={{ color: "oklch(0.65 0.03 130)" }}
                        >
                          {ix.programId}
                        </span>
                      </div>
                      {accounts.length > 0 && (
                        <div>
                          <span style={{ color: "oklch(0.40 0.02 130)" }}>
                            Accounts:{" "}
                          </span>
                          <span
                            className="break-all"
                            style={{ color: "oklch(0.60 0.02 130)" }}
                          >
                            {accounts
                              .map((a) => shortenAddress(a))
                              .join(", ")}
                          </span>
                        </div>
                      )}
                      {ix.data && (
                        <div>
                          <span style={{ color: "oklch(0.40 0.02 130)" }}>
                            Data:{" "}
                          </span>
                          <span
                            className="break-all"
                            style={{ color: "oklch(0.60 0.02 130)" }}
                          >
                            {ix.data.length > 64
                              ? `${ix.data.slice(0, 64)}...`
                              : ix.data}
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </PageLayout>
  )
}
