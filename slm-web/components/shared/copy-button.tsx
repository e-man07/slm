"use client"

import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { Copy01Icon, Tick01Icon } from "@hugeicons/core-free-icons"
import { Button } from "@/components/ui/button"

interface CopyButtonProps {
  value: string
  className?: string
}

export function CopyButton({ value, className }: CopyButtonProps) {
  const [copied, setCopied] = React.useState(false)

  const handleCopy = React.useCallback(async () => {
    await navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [value])

  return (
    <Button
      variant="ghost"
      size="icon-xs"
      onClick={handleCopy}
      className={className}
      aria-label={copied ? "Copied" : "Copy to clipboard"}
    >
      <HugeiconsIcon
        icon={copied ? Tick01Icon : Copy01Icon}
        size={14}
        className={copied ? "text-chart-1" : "text-muted-foreground"}
      />
    </Button>
  )
}
