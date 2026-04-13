"use client"

import * as React from "react"

interface DayStats {
  date: string
  requests: number
  tokens: number
}

interface UsageChartProps {
  data: DayStats[]
}

/**
 * Simple div-based bar chart for 7-day usage.
 * No chart library required.
 */
export function UsageChart({ data }: UsageChartProps) {
  if (data.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No usage data yet.</p>
    )
  }

  const maxRequests = Math.max(...data.map((d) => d.requests), 1)

  // Ensure 7 days are shown (pad with zeros)
  const days: DayStats[] = []
  for (let i = 6; i >= 0; i--) {
    const date = new Date()
    date.setDate(date.getDate() - i)
    const dateStr = date.toISOString().slice(0, 10)
    const existing = data.find((d) => d.date === dateStr)
    days.push(existing ?? { date: dateStr, requests: 0, tokens: 0 })
  }

  return (
    <div className="space-y-2" data-testid="usage-chart">
      <div className="flex items-end gap-1" style={{ height: 120 }}>
        {days.map((day) => {
          const height = Math.max((day.requests / maxRequests) * 100, 2)
          const label = new Date(day.date + "T00:00:00").toLocaleDateString(
            "en-US",
            { weekday: "short" },
          )
          return (
            <div
              key={day.date}
              className="flex flex-1 flex-col items-center gap-1"
            >
              <span className="text-xs text-muted-foreground">
                {day.requests > 0 ? day.requests : ""}
              </span>
              <div
                className="w-full rounded-sm bg-primary/80"
                style={{ height: `${height}%` }}
                title={`${day.date}: ${day.requests} requests, ${day.tokens} tokens`}
              />
              <span className="text-xs text-muted-foreground">{label}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
