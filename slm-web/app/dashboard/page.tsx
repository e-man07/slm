"use client"

import * as React from "react"
import Link from "next/link"
import { useSession, signOut } from "next-auth/react"
import { PageLayout } from "@/components/shared/page-layout"
import { SignInButtons } from "@/components/auth/sign-in-buttons"
import { RATE_LIMITS, type RateLimitTier } from "@/lib/constants"

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type SessionUser = any

interface UsageDay {
  date: string
  requests: number
  tokens: number
}

interface EndpointUsage {
  endpoint: string
  requests: number
  tokens: number
}

interface SourceUsage {
  requests: number
  tokens: number
}

interface UsageData {
  today: { requests: number; tokens: number }
  last_7_days: UsageDay[]
  by_endpoint: EndpointUsage[]
  by_source: { web: SourceUsage; api: SourceUsage }
}

/* ── helpers ── */
function fmtNum(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return String(n)
}

function maskEmail(email: string) {
  const [local, domain] = email.split("@")
  if (!domain) return email
  return `${local.slice(0, 2)}${"*".repeat(Math.max(0, local.length - 2))}@${domain}`
}

/* ── sub-components ── */

function CardHead({ title, tag, right }: { title: string; tag?: string; right?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between" style={{ padding: "14px 20px", borderBottom: "1px solid var(--border)", fontSize: 13, fontWeight: 600 }}>
      <div className="flex items-center gap-3">
        <span>{title}</span>
        {tag && (
          <span style={{ fontSize: 10, letterSpacing: "0.1em", padding: "2px 8px", border: "1px solid var(--slm-accent)", color: "var(--slm-accent)" }}>
            {tag}
          </span>
        )}
      </div>
      {right && <span style={{ fontSize: 10, letterSpacing: "0.08em", color: "var(--muted-foreground)" }}>{right}</span>}
    </div>
  )
}

function KvRow({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="flex items-center justify-between" style={{ padding: "10px 20px", borderTop: "1px dashed var(--border)", fontSize: 13 }}>
      <span className="text-muted-foreground">{label}</span>
      <span style={accent ? { color: "var(--slm-accent)", fontWeight: 600 } : undefined}>{value}</span>
    </div>
  )
}

function MeterBar({ value, max, label }: { value: number; max: number; label: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0
  return (
    <div style={{ padding: "14px 20px" }}>
      <div className="flex items-baseline justify-between" style={{ fontSize: 13 }}>
        <span className="text-muted-foreground">{label}</span>
        <span className="mono-num font-bold">{fmtNum(value)}<span className="text-muted-foreground font-normal"> / {fmtNum(max)}</span></span>
      </div>
      <div className="mt-2" style={{ height: 4, background: "var(--muted)" }}>
        <div style={{ height: "100%", width: `${pct}%`, background: "var(--slm-accent)" }} />
      </div>
    </div>
  )
}

/* ── Usage data hook ── */
function useUsageData(isAuthenticated: boolean) {
  const [data, setData] = React.useState<UsageData | null>(null)
  const [loading, setLoading] = React.useState(false)

  React.useEffect(() => {
    if (!isAuthenticated) return
    const fetchUsage = () => {
      setLoading(true)
      fetch("/api/usage")
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => setData(d ?? null))
        .catch(() => setData(null))
        .finally(() => setLoading(false))
    }
    fetchUsage()
    const interval = setInterval(fetchUsage, 30_000) // refresh every 30s
    return () => clearInterval(interval)
  }, [isAuthenticated])

  return { data, loading }
}

const ENDPOINT_LABELS: Record<string, string> = {
  "/api/chat": "Chat",
  "/api/explain/tx": "Tx Explain",
  "/api/explain/error": "Error Decode",
}

export default function DashboardPage() {
  const { data: session, status } = useSession()
  const [showKey, setShowKey] = React.useState(false)
  const [copied, setCopied] = React.useState(false)
  const [keyLoading, setKeyLoading] = React.useState(false)
  const [localKey, setLocalKey] = React.useState<string | null>(null)

  const user = session?.user as SessionUser | undefined
  const activeKey = localKey ?? (user?.apiKey as string | null)
  const tier = (user?.tier ?? "anonymous") as RateLimitTier

  const { data: usageData, loading: usageLoading } = useUsageData(!!user)

  const handleCopy = React.useCallback(async () => {
    if (!activeKey) return
    await navigator.clipboard.writeText(activeKey)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [activeKey])

  const handleGenerateKey = React.useCallback(async () => {
    setKeyLoading(true)
    try {
      const res = await fetch("/api/key", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "generate" }),
      })
      if (res.ok) {
        const data = await res.json()
        setLocalKey(data.apiKey)
      }
    } finally {
      setKeyLoading(false)
    }
  }, [])

  const handleRotateKey = React.useCallback(async () => {
    if (!confirm("Rotate your API key? The old key will stop working immediately.")) return
    setKeyLoading(true)
    try {
      const res = await fetch("/api/key", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "rotate" }),
      })
      if (res.ok) {
        const data = await res.json()
        setLocalKey(data.apiKey)
        setShowKey(true) // show the new key immediately
      }
    } finally {
      setKeyLoading(false)
    }
  }, [])

  // Usage stats from real data
  const todayTokens = usageData?.today.tokens ?? 0
  const todayReqs = usageData?.today.requests ?? 0
  const days = usageData?.last_7_days ?? []
  const epData = usageData?.by_endpoint ?? []
  const webUsage = usageData?.by_source?.web ?? { requests: 0, tokens: 0 }
  const apiUsage = usageData?.by_source?.api ?? { requests: 0, tokens: 0 }
  const totalTokens7d = days.reduce((s, d) => s + d.tokens, 0)
  const totalReqs7d = days.reduce((s, d) => s + d.requests, 0)
  const tierLimits = RATE_LIMITS[tier]
  const quotaPct = tierLimits.tokensPerDay > 0 && tierLimits.tokensPerDay !== Infinity
    ? Math.round((todayTokens / tierLimits.tokensPerDay) * 100)
    : 0
  const maxBarTokens = Math.max(...days.map((d) => d.tokens), 1)

  /* ── loading ── */
  if (status === "loading") {
    return (
      <PageLayout>
        <div className="py-12">
          <div className="eyebrow">05 / dashboard</div>
          <div className="mt-4" style={{ height: 32, width: 160, background: "var(--muted)" }} />
          <div className="mt-6" style={{ height: 400, background: "var(--muted)" }} />
        </div>
      </PageLayout>
    )
  }

  /* ── not signed in ── */
  if (!user) {
    return (
      <PageLayout>
        <div className="mx-auto max-w-md py-12">
          <div className="eyebrow">05 / dashboard</div>
          <h1 className="mt-4 font-bold" style={{ fontSize: 32 }}>Dashboard.</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Sign in to get your API key, track usage, and save chat history.
          </p>
          <div className="mt-8" style={{ border: "1px solid var(--border)" }}>
            <CardHead title="Sign in" />
            <div style={{ padding: 20 }}>
              <SignInButtons />
            </div>
          </div>
        </div>
      </PageLayout>
    )
  }

  /* ── signed in ── */
  return (
    <PageLayout>
      <div className="py-12">
        {/* ── header ── */}
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="eyebrow">05 / dashboard</div>
            <h1 className="mt-3 font-bold" style={{ fontSize: 32 }}>Dashboard.</h1>
            <p className="mt-1 text-sm text-muted-foreground">Your key, your usage, your limits.</p>
          </div>
          <div className="flex gap-2">
            {activeKey && (
              <button
                onClick={handleRotateKey}
                disabled={keyLoading}
                style={{ fontSize: 12, padding: "6px 10px", border: "1px solid var(--border)" }}
                className="text-muted-foreground transition-colors hover:text-foreground hover:bg-muted disabled:opacity-50"
              >
                {keyLoading ? "..." : "Rotate key"}
              </button>
            )}
            <button
              onClick={() => signOut({ callbackUrl: "/" })}
              style={{ fontSize: 12, padding: "6px 10px", border: "1px solid var(--border)" }}
              className="text-muted-foreground transition-colors hover:text-foreground hover:bg-muted"
            >
              Sign out
            </button>
          </div>
        </div>

        {/* ── main grid ── */}
        <div className="mt-10 grid grid-cols-1 lg:grid-cols-[2fr_1fr]" style={{ border: "1px solid var(--border)" }}>
          {/* ═══ LEFT COLUMN ═══ */}
          <div style={{ borderRight: "1px solid var(--border)" }}>

            {/* ── API Key card ── */}
            <div style={{ borderBottom: "1px solid var(--border)" }}>
              <CardHead title="API Key" tag={activeKey ? "ACTIVE" : undefined} />
              <div style={{ padding: 20 }}>
                {activeKey ? (
                  <>
                    <div className="terminal-bg flex items-center gap-2 font-mono text-sm" style={{ padding: "10px 14px" }}>
                      <span className="slm-accent">slm_</span>
                      <span className="flex-1 tracking-wider">
                        {showKey ? activeKey.slice(4) : `${"*".repeat(Math.max(0, activeKey.length - 8))}${activeKey.slice(-4)}`}
                      </span>
                      <button
                        onClick={() => setShowKey(!showKey)}
                        style={{ fontSize: 10, letterSpacing: "0.08em", padding: "3px 8px", border: "1px solid var(--border)" }}
                        className="text-muted-foreground hover:text-foreground"
                      >
                        {showKey ? "HIDE" : "SHOW"}
                      </button>
                      <button
                        onClick={handleCopy}
                        style={{ fontSize: 10, letterSpacing: "0.08em", padding: "3px 8px", border: "1px solid var(--border)" }}
                        className="text-muted-foreground hover:text-foreground"
                      >
                        {copied ? "COPIED" : "COPY"}
                      </button>
                    </div>
                    <p className="mt-3 text-muted-foreground" style={{ fontSize: 11 }}>
                      Use in the Authorization header: <code className="bg-muted px-1 py-0.5 text-[10px]">Bearer {"<key>"}</code>
                    </p>
                  </>
                ) : (
                  <div className="text-center py-6">
                    <p className="text-sm text-muted-foreground mb-4">
                      Generate an API key to use Sealevel from the CLI, MCP, or any OpenAI-compatible client.
                    </p>
                    <button
                      onClick={handleGenerateKey}
                      disabled={keyLoading}
                      className="disabled:opacity-50"
                      style={{ fontSize: 13, padding: "10px 20px", background: "var(--slm-accent)", color: "oklch(0.153 0.006 107.1)", fontWeight: 600 }}
                    >
                      {keyLoading ? "Generating..." : "Generate API Key"}
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* ── Usage card ── */}
            <div style={{ borderBottom: "1px solid var(--border)" }}>
              <CardHead title="Usage &middot; last 7 days" right="tokens/day" />
              <div style={{ padding: 20 }}>
                {usageLoading ? (
                  <div style={{ height: 100 }} className="flex items-center justify-center text-xs text-muted-foreground">Loading...</div>
                ) : days.length === 0 ? (
                  <div style={{ height: 100 }} className="flex items-center justify-center text-xs text-muted-foreground">No usage yet</div>
                ) : (
                  <>
                    {/* Bar chart */}
                    <div className="flex items-end gap-[3px]" style={{ height: 100 }}>
                      {days.map((d, i) => {
                        const h = Math.max((d.tokens / maxBarTokens) * 100, 4)
                        const isToday = i === days.length - 1
                        return (
                          <div
                            key={d.date}
                            className="flex-1"
                            title={`${d.date}: ${d.tokens} tokens, ${d.requests} requests`}
                            style={{ height: `${h}%`, background: isToday ? "var(--slm-accent)" : "var(--slm-accent-dim)", opacity: isToday ? 1 : 0.7 }}
                          />
                        )
                      })}
                    </div>
                    {/* X-axis */}
                    <div className="mt-2 flex justify-between" style={{ fontSize: 9, color: "var(--muted-foreground)" }}>
                      <span>{days[0]?.date}</span>
                      <span>{days[days.length - 1]?.date}</span>
                    </div>
                  </>
                )}
                {/* Stats row */}
                <div className="mt-4 grid grid-cols-4" style={{ border: "1px solid var(--border)" }}>
                  {[
                    { value: fmtNum(totalTokens7d), label: "Tokens 7d" },
                    { value: String(totalReqs7d), label: "Requests 7d" },
                    { value: fmtNum(todayTokens), label: "Tokens today" },
                    { value: `${quotaPct}%`, label: "Of quota" },
                  ].map((s, i) => (
                    <div key={s.label} style={{ padding: "10px 12px", borderRight: i < 3 ? "1px solid var(--border)" : "none" }}>
                      <div className="mono-num font-bold" style={{ fontSize: 16 }}>{s.value}</div>
                      <div style={{ fontSize: 9, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--muted-foreground)", marginTop: 2 }}>{s.label}</div>
                    </div>
                  ))}
                </div>
                {/* Web vs API breakdown */}
                {(webUsage.tokens > 0 || apiUsage.tokens > 0) && (
                  <div className="mt-4 grid grid-cols-2" style={{ border: "1px solid var(--border)" }}>
                    <div style={{ padding: "12px 16px", borderRight: "1px solid var(--border)" }}>
                      <div style={{ fontSize: 9, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--muted-foreground)", marginBottom: 6 }}>
                        Web usage
                      </div>
                      <div className="mono-num font-bold" style={{ fontSize: 18 }}>{fmtNum(webUsage.tokens)}</div>
                      <div style={{ fontSize: 10, color: "var(--muted-foreground)", marginTop: 2 }}>{webUsage.requests} requests</div>
                      <div className="mt-2" style={{ height: 3, background: "var(--muted)" }}>
                        <div style={{ height: "100%", width: `${totalTokens7d > 0 ? Math.round((webUsage.tokens / totalTokens7d) * 100) : 0}%`, background: "var(--slm-accent)" }} />
                      </div>
                    </div>
                    <div style={{ padding: "12px 16px" }}>
                      <div style={{ fontSize: 9, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--muted-foreground)", marginBottom: 6 }}>
                        API usage
                      </div>
                      <div className="mono-num font-bold" style={{ fontSize: 18 }}>{fmtNum(apiUsage.tokens)}</div>
                      <div style={{ fontSize: 10, color: "var(--muted-foreground)", marginTop: 2 }}>{apiUsage.requests} requests</div>
                      <div className="mt-2" style={{ height: 3, background: "var(--muted)" }}>
                        <div style={{ height: "100%", width: `${totalTokens7d > 0 ? Math.round((apiUsage.tokens / totalTokens7d) * 100) : 0}%`, background: "var(--slm-accent)" }} />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* ── Rate limits card ── */}
            <div>
              <CardHead title="Your limits" right="free plan" />
              <div className="grid grid-cols-2">
                <div style={{ borderRight: "1px solid var(--border)" }}>
                  <MeterBar value={todayReqs} max={tierLimits.requestsPerMin * 1440} label="Requests today" />
                  <p style={{ padding: "0 20px 14px", fontSize: 10, color: "var(--muted-foreground)" }}>
                    Rate limit: {tierLimits.requestsPerMin} req/min ({fmtNum(tierLimits.requestsPerMin * 1440)}/day max)
                  </p>
                </div>
                <div>
                  <MeterBar
                    value={todayTokens}
                    max={tierLimits.tokensPerDay === Infinity ? 1 : tierLimits.tokensPerDay}
                    label="Tokens today"
                  />
                  <p style={{ padding: "0 20px 14px", fontSize: 10, color: "var(--muted-foreground)" }}>
                    Limit: {fmtNum(tierLimits.tokensPerDay)} tokens/day
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* ═══ RIGHT COLUMN ═══ */}
          <div>
            {/* ── Account card ── */}
            <div style={{ borderBottom: "1px solid var(--border)" }}>
              <CardHead title="Account" tag={(user.provider ?? "GITHUB").toUpperCase()} />
              <div>
                <KvRow label="Name" value={user.name ?? "\u2014"} />
                <KvRow label="Email" value={user.email ? maskEmail(user.email) : "\u2014"} />
                <KvRow label="Tier" value={tier.toUpperCase()} accent />
              </div>
            </div>

            {/* ── Quickstart card ── */}
            <div>
              <CardHead title="Quickstart" />
              <div style={{ padding: 20 }}>
                <pre className="terminal-bg overflow-x-auto font-mono" style={{ padding: "14px 16px", fontSize: 11, lineHeight: 1.7 }}>
                  <code>
                    <span className="t-prompt">$</span>
                    {` curl -X POST https://api.sealevel.tech/v1/chat \\`}
                    {"\n"}
                    {"  "}<span className="t-key">-H</span> <span className="t-str">{`"Authorization: Bearer ${activeKey ? activeKey.slice(0, 8) + "..." : "slm_xxx"}"`}</span> {`\\`}
                    {"\n"}
                    {"  "}<span className="t-key">-H</span> <span className="t-str">{`"Content-Type: application/json"`}</span> {`\\`}
                    {"\n"}
                    {"  "}<span className="t-key">-d</span> <span className="t-str">{`'{"messages": [{"role": "user", "content": "Hello"}]}'`}</span>
                  </code>
                </pre>
                <p className="mt-3 text-muted-foreground" style={{ fontSize: 11 }}>
                  See the{" "}
                  <Link href="/docs" className="text-foreground underline underline-offset-2">full API docs</Link>
                  {" "}for more examples.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </PageLayout>
  )
}
