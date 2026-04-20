"use client"

import * as React from "react"
import Link from "next/link"
import { useSession, signOut } from "next-auth/react"
import { PageLayout } from "@/components/shared/page-layout"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { ApiKeyDisplay } from "@/components/dashboard/api-key-display"
import { UsageStats } from "@/components/dashboard/usage-stats"
import { SignInButtons } from "@/components/auth/sign-in-buttons"
import { useApiKey } from "@/hooks/use-api-key"

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type SessionUser = any

export default function DashboardPage() {
  const { data: session, status } = useSession()
  const { apiKey: localKey, setKey, clearKey } = useApiKey()
  const [inputKey, setInputKey] = React.useState("")

  const user = session?.user as SessionUser | undefined
  // Prefer server-issued key (from OAuth), fall back to manually entered local key
  const activeKey = user?.apiKey ?? localKey
  const tier = user?.tier ?? (localKey ? "free" : "anonymous")

  const handleSave = React.useCallback(() => {
    const trimmed = inputKey.trim()
    if (trimmed) {
      setKey(trimmed)
      setInputKey("")
    }
  }, [inputKey, setKey])

  // Loading state
  if (status === "loading") {
    return (
      <PageLayout>
        <div className="space-y-6">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      </PageLayout>
    )
  }

  // Not signed in — show sign-in prompt
  if (!user) {
    return (
      <PageLayout>
        <div className="mx-auto max-w-md space-y-6">
          <div>
            <h1 className="text-2xl font-bold">Dashboard</h1>
            <p className="mt-1 text-muted-foreground">
              Sign in to get your API key, track usage, and save chat history.
            </p>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Sign in</CardTitle>
              <CardDescription>Use GitHub or Google to continue.</CardDescription>
            </CardHeader>
            <CardContent>
              <SignInButtons />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Have an API key already?</CardTitle>
              <CardDescription>
                Paste it below to use higher rate limits without signing in.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {localKey ? (
                <div className="space-y-3">
                  <ApiKeyDisplay apiKey={localKey} />
                  <Button variant="outline" size="sm" onClick={clearKey}>
                    Remove key
                  </Button>
                </div>
              ) : (
                <div className="flex gap-2">
                  <Input
                    value={inputKey}
                    onChange={(e) => setInputKey(e.target.value)}
                    placeholder="slm_xxxxxxxxxxxx"
                    className="font-mono"
                    onKeyDown={(e) => e.key === "Enter" && handleSave()}
                  />
                  <Button onClick={handleSave} disabled={!inputKey.trim()}>
                    Save
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </PageLayout>
    )
  }

  // Signed in
  return (
    <PageLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Dashboard</h1>
            <p className="mt-1 text-muted-foreground">
              Manage your API key and view usage
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => signOut({ callbackUrl: "/" })}>
            Sign out
          </Button>
        </div>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">Account</CardTitle>
                <CardDescription>{user.email ?? "No email"}</CardDescription>
              </div>
              <Badge variant="outline" className="capitalize">
                {user.provider ?? "oauth"}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Name</span>
              <span>{user.name ?? "—"}</span>
            </div>
            <Separator />
            <div className="flex justify-between">
              <span className="text-muted-foreground">Tier</span>
              <Badge variant="default" className="capitalize">
                {tier}
              </Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">API Key</CardTitle>
                <CardDescription>
                  Use this in the Authorization header: <code>Bearer {"<key>"}</code>
                </CardDescription>
              </div>
              <Badge variant="outline">Active</Badge>
            </div>
          </CardHeader>
          <CardContent>
            {activeKey ? (
              <ApiKeyDisplay apiKey={activeKey} />
            ) : (
              <p className="text-sm text-muted-foreground">
                Your key is being provisioned — refresh the page.
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Rate Limits</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Requests/min</span>
              <span>{tier === "standard" ? "30" : tier === "admin" ? "100" : "10"}</span>
            </div>
            <Separator />
            <div className="flex justify-between">
              <span className="text-muted-foreground">Tokens/day</span>
              <span>
                {tier === "standard" ? "500K" : tier === "admin" ? "Unlimited" : "50K"}
              </span>
            </div>
          </CardContent>
        </Card>

        <UsageStats apiKey={activeKey ?? ""} />

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Quick Start</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <p>Use your API key in requests:</p>
            <pre className="overflow-x-auto bg-muted p-3 text-xs">
              <code>{`curl -X POST https://slm.dev/api/chat \\
  -H "Authorization: Bearer ${activeKey || "slm_xxxx"}" \\
  -H "Content-Type: application/json" \\
  -d '{"messages": [{"role": "user", "content": "Hello"}]}'`}</code>
            </pre>
            <p>
              See the{" "}
              <Link href="/docs" className="text-foreground underline underline-offset-2">
                full API docs
              </Link>{" "}
              for more examples.
            </p>
          </CardContent>
        </Card>
      </div>
    </PageLayout>
  )
}
