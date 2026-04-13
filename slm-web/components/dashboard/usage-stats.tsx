"use client"

import * as React from "react"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { UsageChart } from "./usage-chart"

interface DayStats {
  date: string
  requests: number
  tokens: number
}

interface UsageStatsProps {
  apiKey: string
}

/**
 * Fetches and displays API usage stats for the authenticated user.
 */
export function UsageStats({ apiKey }: UsageStatsProps) {
  const [loading, setLoading] = React.useState(true)
  const [todayRequests, setTodayRequests] = React.useState(0)
  const [todayTokens, setTodayTokens] = React.useState(0)
  const [weekData, setWeekData] = React.useState<DayStats[]>([])
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    async function fetchStats() {
      try {
        const response = await fetch("/api/usage", {
          headers: {
            Authorization: `Bearer ${apiKey}`,
          },
        })

        if (!response.ok) {
          setError("Failed to load usage stats")
          setLoading(false)
          return
        }

        const data = await response.json()
        setTodayRequests(data.today?.requests ?? 0)
        setTodayTokens(data.today?.tokens ?? 0)
        setWeekData(data.last_7_days ?? [])
      } catch {
        setError("Failed to connect")
      } finally {
        setLoading(false)
      }
    }

    if (apiKey) {
      fetchStats()
    } else {
      setLoading(false)
    }
  }, [apiKey])

  if (!apiKey) {
    return null
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Usage</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading stats...</p>
        ) : error ? (
          <p className="text-sm text-destructive">{error}</p>
        ) : (
          <>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Requests today</span>
                <span data-testid="requests-today">{todayRequests}</span>
              </div>
              <Separator />
              <div className="flex justify-between">
                <span className="text-muted-foreground">Tokens used today</span>
                <span data-testid="tokens-today">
                  {todayTokens.toLocaleString()}
                </span>
              </div>
            </div>
            <Separator />
            <div>
              <p className="mb-2 text-sm font-medium">Last 7 days</p>
              <UsageChart data={weekData} />
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
