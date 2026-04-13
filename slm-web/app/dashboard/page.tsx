"use client"

import * as React from "react"
import { PageLayout } from "@/components/shared/page-layout"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { ApiKeyDisplay } from "@/components/dashboard/api-key-display"
import { UsageStats } from "@/components/dashboard/usage-stats"
import { useApiKey } from "@/hooks/use-api-key"

export default function DashboardPage() {
  const { apiKey, setKey, clearKey } = useApiKey()
  const [inputKey, setInputKey] = React.useState("")

  const handleSave = React.useCallback(() => {
    const trimmed = inputKey.trim()
    if (trimmed) {
      setKey(trimmed)
      setInputKey("")
    }
  }, [inputKey, setKey])

  const handleClear = React.useCallback(() => {
    clearKey()
  }, [clearKey])

  return (
    <PageLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="mt-1 text-muted-foreground">
            Manage your API key and view usage
          </p>
        </div>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">API Key</CardTitle>
                <CardDescription>
                  Your key is stored locally in this browser
                </CardDescription>
              </div>
              <Badge variant="outline">
                {apiKey ? "Configured" : "Not set"}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {apiKey ? (
              <>
                <ApiKeyDisplay apiKey={apiKey} />
                <Button variant="outline" size="sm" onClick={handleClear}>
                  Remove key
                </Button>
              </>
            ) : (
              <div className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  Enter your API key to increase rate limits. Without a key,
                  anonymous limits apply (5 req/min, 10K tokens/day).
                </p>
                <div className="flex gap-2">
                  <Input
                    value={inputKey}
                    onChange={(e) => setInputKey(e.target.value)}
                    placeholder="slm_xxxxxxxxxxxx"
                    className="max-w-sm font-mono"
                    onKeyDown={(e) => e.key === "Enter" && handleSave()}
                  />
                  <Button onClick={handleSave} disabled={!inputKey.trim()}>
                    Save
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Rate Limits</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Current tier</span>
              <Badge variant={apiKey ? "default" : "outline"}>
                {apiKey ? "Free" : "Anonymous"}
              </Badge>
            </div>
            <Separator />
            <div className="flex justify-between">
              <span className="text-muted-foreground">Requests/min</span>
              <span>{apiKey ? "10" : "5"}</span>
            </div>
            <Separator />
            <div className="flex justify-between">
              <span className="text-muted-foreground">Tokens/day</span>
              <span>{apiKey ? "50K" : "10K"}</span>
            </div>
          </CardContent>
        </Card>

        <UsageStats apiKey={apiKey} />

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Quick Start</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <p>Use your API key in requests:</p>
            <pre className="overflow-x-auto bg-muted p-3 text-xs">
              <code>{`curl -X POST https://slm.dev/api/chat \\
  -H "Authorization: Bearer ${apiKey || "slm_xxxx"}" \\
  -H "Content-Type: application/json" \\
  -d '{"messages": [{"role": "user", "content": "Hello"}]}'`}</code>
            </pre>
          </CardContent>
        </Card>
      </div>
    </PageLayout>
  )
}
