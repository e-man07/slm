"use client"

import * as React from "react"
import { cn } from "@/lib/utils"

interface TxSignatureInputProps {
  onSubmit: (signature: string) => void
  isLoading?: boolean
  className?: string
}

const EXAMPLE_SIGNATURE =
  "5UfDuX7WXYxjng1PYLJmzGRqaWEd7dMN5Ld5sgsMUPoStSK7F4EzPbf2jnEHrgTCFm1GZeKVgU9LnE2RXm8S8Bu"

function isValidBase58(str: string): boolean {
  return /^[1-9A-HJ-NP-Za-km-z]{87,88}$/.test(str)
}

export function TxSignatureInput({
  onSubmit,
  isLoading = false,
  className,
}: TxSignatureInputProps) {
  const [value, setValue] = React.useState("")
  const [error, setError] = React.useState("")

  const handleSubmit = React.useCallback(() => {
    const trimmed = value.trim()
    if (!trimmed) {
      setError("Please enter a transaction signature")
      return
    }
    if (!isValidBase58(trimmed)) {
      setError("Invalid transaction signature format")
      return
    }
    setError("")
    onSubmit(trimmed)
  }, [value, onSubmit])

  const handlePaste = React.useCallback(async () => {
    const text = await navigator.clipboard.readText()
    setValue(text.trim())
    setError("")
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

  return (
    <div className={cn("space-y-2", className)}>
      <div
        className="border bg-card"
        style={{ borderColor: "var(--slm-border-strong)" }}
      >
        <div className="flex items-center gap-2 px-3.5 py-1.5">
          <span className="font-semibold slm-accent">$</span>
          <input
            value={value}
            onChange={(e) => { setValue(e.target.value); setError("") }}
            onKeyDown={handleKeyDown}
            placeholder="5UfDuX7WXYxjng1PYLJmzGRq..."
            className="flex-1 bg-transparent border-0 outline-none text-[13px] py-2.5 px-1.5 placeholder:text-muted-foreground"
            disabled={isLoading}
          />
          <button
            onClick={handleSubmit}
            disabled={isLoading || !value.trim()}
            className="inline-flex items-center gap-2 px-3 py-2 text-xs font-medium tracking-[0.02em] transition-all disabled:opacity-50"
            style={{
              background: "var(--slm-accent)",
              color: "oklch(0.153 0.006 107.1)",
            }}
          >
            Explain <span>&rarr;</span>
          </button>
        </div>
        <div className="flex items-center justify-between border-t border-border px-3.5 py-2 text-[11px] text-muted-foreground">
          <div className="flex items-center gap-3">
            <span>{value.length} chars &middot; base58</span>
            <button
              onClick={() => { setValue(EXAMPLE_SIGNATURE); setError("") }}
              className="underline underline-offset-2 hover:text-foreground"
            >
              try example
            </button>
            <button onClick={handlePaste} className="hover:text-foreground">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" style={{ verticalAlign: "-1px", display: "inline" }}>
                <rect x="9" y="9" width="13" height="13" /><path d="M5 15V4a2 2 0 0 1 2-2h11" />
              </svg>{" "}paste
            </button>
          </div>
          <span><span className="kbd">&thinsp;&crarr;&thinsp;</span> to submit</span>
        </div>
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}
