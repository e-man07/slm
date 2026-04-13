"use client"

import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { ClipboardIcon, Search01Icon } from "@hugeicons/core-free-icons"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
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
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Input
            value={value}
            onChange={(e) => {
              setValue(e.target.value)
              setError("")
            }}
            onKeyDown={handleKeyDown}
            placeholder="Paste a Solana transaction signature..."
            className={cn(error && "border-destructive")}
            disabled={isLoading}
          />
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={handlePaste}
            className="absolute right-2 top-1/2 -translate-y-1/2"
            aria-label="Paste from clipboard"
          >
            <HugeiconsIcon icon={ClipboardIcon} size={14} />
          </Button>
        </div>
        <Button onClick={handleSubmit} disabled={isLoading || !value.trim()}>
          <HugeiconsIcon icon={Search01Icon} size={16} />
          Explain
        </Button>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <button
        type="button"
        onClick={() => {
          setValue(EXAMPLE_SIGNATURE)
          setError("")
        }}
        className="text-xs text-muted-foreground underline-offset-4 hover:underline"
      >
        Try an example transaction
      </button>
    </div>
  )
}
