"use client"

import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { Copy01Icon, Tick01Icon, ViewIcon, ViewOffIcon } from "@hugeicons/core-free-icons"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

interface ApiKeyDisplayProps {
  apiKey: string
  className?: string
}

export function ApiKeyDisplay({ apiKey, className }: ApiKeyDisplayProps) {
  const [visible, setVisible] = React.useState(false)
  const [copied, setCopied] = React.useState(false)

  const maskedKey = apiKey
    ? `${apiKey.slice(0, 8)}${"*".repeat(Math.max(0, apiKey.length - 12))}${apiKey.slice(-4)}`
    : ""

  const handleCopy = React.useCallback(async () => {
    await navigator.clipboard.writeText(apiKey)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [apiKey])

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <Input
        readOnly
        value={visible ? apiKey : maskedKey}
        className="font-mono text-sm"
      />
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setVisible(!visible)}
        aria-label={visible ? "Hide key" : "Show key"}
      >
        <HugeiconsIcon icon={visible ? ViewOffIcon : ViewIcon} size={16} />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        onClick={handleCopy}
        aria-label={copied ? "Copied" : "Copy key"}
      >
        <HugeiconsIcon
          icon={copied ? Tick01Icon : Copy01Icon}
          size={16}
          className={copied ? "text-chart-1" : ""}
        />
      </Button>
    </div>
  )
}
