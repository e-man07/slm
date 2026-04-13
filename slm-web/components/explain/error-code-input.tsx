"use client"

import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { Search01Icon } from "@hugeicons/core-free-icons"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
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
    <div className={cn("space-y-3", className)}>
      <div className="flex gap-2">
        <Input
          value={errorCode}
          onChange={(e) => {
            setErrorCode(e.target.value)
            setError("")
          }}
          onKeyDown={handleKeyDown}
          placeholder="Error code (e.g., 0x7D0 or 2000)"
          className={cn("max-w-[240px]", error && "border-destructive")}
          disabled={isLoading}
        />
        <Input
          value={programId}
          onChange={(e) => setProgramId(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Program ID (optional)"
          disabled={isLoading}
        />
        <Button onClick={handleSubmit} disabled={isLoading || !errorCode.trim()}>
          <HugeiconsIcon icon={Search01Icon} size={16} />
          Decode
        </Button>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="flex flex-wrap gap-2">
        <span className="text-xs text-muted-foreground">Common:</span>
        {POPULAR_ERRORS.map((err) => (
          <Badge
            key={err.code}
            variant="outline"
            className="cursor-pointer text-xs transition-colors hover:bg-accent"
            onClick={() => {
              setErrorCode(err.code)
              setError("")
            }}
          >
            {err.code} {err.label}
          </Badge>
        ))}
      </div>
    </div>
  )
}
