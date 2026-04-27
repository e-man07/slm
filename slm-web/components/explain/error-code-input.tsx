"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { isValidErrorCode } from "@/lib/errors"

interface ErrorCodeInputProps {
  onSubmit: (errorCode: string, programId?: string) => void
  isLoading?: boolean
  className?: string
}

const POPULAR_ERRORS = [
  { code: "0x7D0", label: "ConstraintMut" },
  { code: "0x7D3", label: "ConstraintSeeds" },
  { code: "0xBC4", label: "AccountNotInitialized" },
  { code: "0x7D1", label: "ConstraintHasOne" },
  { code: "0x7D6", label: "ConstraintOwner" },
]

export function ErrorCodeInput({
  onSubmit,
  isLoading = false,
  className,
}: ErrorCodeInputProps) {
  const [errorCode, setErrorCode] = React.useState("")
  const [programId, setProgramId] = React.useState("")
  const [error, setError] = React.useState("")

  const handleSubmit = React.useCallback(() => {
    if (!errorCode.trim()) {
      setError("Please enter an error code")
      return
    }
    if (!isValidErrorCode(errorCode.trim())) {
      setError("Invalid error code format (use hex like 0x7D0 or decimal like 2000)")
      return
    }
    setError("")
    onSubmit(errorCode.trim(), programId.trim() || undefined)
  }, [errorCode, programId, onSubmit])

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
    <div className={cn("space-y-4", className)}>
      {/* Input row */}
      <div
        className="border bg-card"
        style={{ borderColor: "var(--slm-border-strong)" }}
      >
        <div className="flex flex-col gap-0 sm:flex-row sm:items-center sm:gap-2 px-3.5 py-1.5">
          <div className="flex flex-1 items-center gap-2">
            <span className="font-semibold slm-accent">$</span>
            <input
              value={errorCode}
              onChange={(e) => { setErrorCode(e.target.value); setError("") }}
              onKeyDown={handleKeyDown}
              placeholder="Error code (0x7D0 or 2000)"
              aria-label="Error code"
              name="errorCode"
              autoComplete="off"
              spellCheck={false}
              className="flex-1 bg-transparent border-0 outline-none focus-visible:outline-none text-[13px] py-2.5 px-1.5 placeholder:text-muted-foreground"
              disabled={isLoading}
            />
          </div>
          <div className="flex flex-1 items-center gap-2 border-t border-border sm:border-t-0 sm:border-l">
            <input
              value={programId}
              onChange={(e) => setProgramId(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Program ID (optional)"
              aria-label="Program ID"
              name="programId"
              autoComplete="off"
              spellCheck={false}
              className="flex-1 bg-transparent border-0 outline-none focus-visible:outline-none text-[13px] py-2.5 px-3 placeholder:text-muted-foreground"
              disabled={isLoading}
            />
            <button
              onClick={handleSubmit}
              disabled={isLoading || !errorCode.trim()}
              className="inline-flex shrink-0 items-center gap-2 px-3 py-2 text-xs font-medium tracking-[0.02em] transition-all disabled:opacity-50"
              style={{
                background: "var(--slm-accent)",
                color: "oklch(0.153 0.006 107.1)",
              }}
            >
              Decode <span>&rarr;</span>
            </button>
          </div>
        </div>
        <div className="flex items-center justify-between border-t border-border px-3.5 py-2 text-[11px] text-muted-foreground">
          <span>hex or decimal</span>
          <span><span className="kbd">&thinsp;&crarr;&thinsp;</span> to submit</span>
        </div>
      </div>

      {error && <p className="text-xs text-destructive">{error}</p>}

      {/* Popular errors */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Common:</span>
        {POPULAR_ERRORS.map((err) => (
          <button
            key={err.code}
            className="border border-border px-2 py-1 text-[11px] text-muted-foreground transition-colors hover:text-foreground hover:border-foreground"
            onClick={() => { setErrorCode(err.code); setError("") }}
          >
            {err.code} {err.label}
          </button>
        ))}
      </div>
    </div>
  )
}
