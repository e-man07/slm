"use client"

import * as React from "react"
import Link from "next/link"
import { signIn } from "next-auth/react"
import { useSearchParams } from "next/navigation"
import { NavBar } from "@/components/nav-bar"

/* ── inline SVG icons ── */
function GitHubIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" aria-hidden>
      <path d="M12 .5C5.65.5.5 5.65.5 12a11.5 11.5 0 0 0 7.86 10.92c.57.1.78-.25.78-.55v-2c-3.2.7-3.87-1.37-3.87-1.37-.52-1.33-1.27-1.68-1.27-1.68-1.04-.7.08-.69.08-.69 1.15.08 1.76 1.18 1.76 1.18 1.02 1.75 2.68 1.24 3.33.95.1-.74.4-1.24.73-1.53-2.55-.3-5.24-1.28-5.24-5.7 0-1.26.45-2.3 1.18-3.1-.12-.3-.51-1.47.11-3.07 0 0 .96-.31 3.16 1.18a10.96 10.96 0 0 1 5.75 0c2.2-1.5 3.16-1.18 3.16-1.18.62 1.6.23 2.77.11 3.07.74.8 1.18 1.84 1.18 3.1 0 4.43-2.7 5.4-5.26 5.69.41.36.78 1.06.78 2.14v3.17c0 .3.2.66.79.55A11.5 11.5 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5Z" />
    </svg>
  )
}

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden>
      <path
        fill="#EA4335"
        d="M12 10.2v3.7h5.25c-.23 1.3-1.56 3.8-5.25 3.8-3.16 0-5.74-2.62-5.74-5.86s2.58-5.86 5.74-5.86c1.8 0 3 .76 3.7 1.42l2.52-2.43C16.64 3.46 14.55 2.4 12 2.4 6.72 2.4 2.45 6.68 2.45 12S6.72 21.6 12 21.6c6.93 0 9.55-4.86 9.55-9.34 0-.63-.07-1.11-.15-1.59L12 10.2z"
      />
    </svg>
  )
}

const PROOF_CELLS = [
  { value: "91%", label: "Solana eval" },
  { value: "270K", label: "Training records" },
  { value: "1,914", label: "Errors decoded" },
  { value: "41", label: "Programs covered" },
] as const

const ASCII_ART = `
+--------------------------------------+
|  $ slm "explain this tx"             |
|  > Analyzing transaction...          |
|  > CPI: Token Program -> Transfer    |
|  > Amount: 1.5 SOL                   |
|  > Status: Confirmed                 |
+--------------------------------------+
`.trim()

export default function SignInPage() {
  const searchParams = useSearchParams()
  const callbackUrl = searchParams.get("callbackUrl") ?? "/dashboard"
  const [tab, setTab] = React.useState<"sign-in" | "create">("sign-in")
  const [loading, setLoading] = React.useState<string | null>(null)

  const handleOAuth = async (provider: "github" | "google") => {
    setLoading(provider)
    try {
      await signIn(provider, { callbackUrl })
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="flex min-h-svh flex-col">
      <NavBar minimal />

      <div className="flex flex-1" style={{ borderTop: "1px solid var(--border)" }}>
        {/* ══ LEFT COLUMN ══ */}
        <div
          className="hidden flex-col justify-between lg:flex"
          style={{
            flex: "1 1 50%",
            background: "var(--card)",
            borderRight: "1px solid var(--border)",
            padding: "60px 64px",
          }}
        >
          {/* Top */}
          <div>
            <div className="eyebrow" style={{ color: "var(--slm-accent)" }}>
              SEALEVEL / AUTH
            </div>

            <h1
              className="mt-5 font-bold leading-[1.05] tracking-[-0.025em]"
              style={{ fontSize: 44, maxWidth: "14ch" }}
            >
              Welcome back, builder.
            </h1>

            <p className="mt-5 max-w-[38ch] text-sm leading-relaxed text-muted-foreground">
              Sign in to access your API key, track usage, and save chat
              history.
            </p>

            {/* 2x2 proof grid */}
            <div
              className="mt-10 grid grid-cols-2"
              style={{ border: "1px solid var(--border)", maxWidth: 360 }}
            >
              {PROOF_CELLS.map((cell, i) => (
                <div
                  key={cell.label}
                  style={{
                    padding: "16px 20px",
                    borderRight: i % 2 === 0 ? "1px solid var(--border)" : "none",
                    borderBottom: i < 2 ? "1px solid var(--border)" : "none",
                  }}
                >
                  <div className="mono-num font-bold" style={{ fontSize: 22 }}>
                    {cell.value}
                  </div>
                  <div
                    className="mt-1"
                    style={{
                      fontSize: 10,
                      letterSpacing: "0.1em",
                      textTransform: "uppercase",
                      color: "var(--muted-foreground)",
                    }}
                  >
                    {cell.label}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Bottom: ASCII art */}
          <pre
            className="mt-8"
            style={{
              fontSize: 12,
              lineHeight: 1.6,
              color: "var(--slm-border-strong)",
              whiteSpace: "pre",
              fontFamily: "var(--font-mono), monospace",
            }}
          >
            {ASCII_ART}
          </pre>
        </div>

        {/* ══ RIGHT COLUMN ══ */}
        <div
          className="flex flex-1 items-center justify-center"
          style={{ padding: "60px 64px" }}
        >
          <div style={{ width: "100%", maxWidth: 520 }}>
            {/* Tabs */}
            <div className="flex" style={{ border: "1px solid var(--border)" }}>
              {(["sign-in", "create"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className="flex-1 transition-colors"
                  style={{
                    padding: "10px 0",
                    fontSize: 12,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    fontWeight: 600,
                    background: tab === t ? "var(--muted)" : "transparent",
                    borderRight: t === "sign-in" ? "1px solid var(--border)" : "none",
                    color: tab === t ? "var(--foreground)" : "var(--muted-foreground)",
                  }}
                >
                  {t === "sign-in" ? "Sign in" : "Create Account"}
                </button>
              ))}
            </div>

            {/* Heading */}
            <h2 className="mt-8 font-bold" style={{ fontSize: 24 }}>
              {tab === "sign-in" ? "Sign in to Sealevel." : "Create your Sealevel account."}
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Pick an OAuth provider to continue.
            </p>

            {/* OAuth buttons */}
            <div className="mt-8 flex flex-col gap-3">
              <button
                onClick={() => handleOAuth("github")}
                disabled={loading !== null}
                className="flex w-full items-center gap-3 transition-colors hover:bg-muted disabled:opacity-50"
                style={{
                  border: "1px solid var(--border)",
                  padding: "12px 16px",
                  fontSize: 14,
                }}
              >
                <GitHubIcon />
                <span className="flex-1 text-left">
                  {loading === "github" ? "Redirecting..." : "Continue with GitHub"}
                </span>
                <span
                  style={{
                    fontSize: 10,
                    letterSpacing: "0.1em",
                    color: "var(--muted-foreground)",
                  }}
                >
                  OAUTH
                </span>
              </button>

              <button
                onClick={() => handleOAuth("google")}
                disabled={loading !== null}
                className="flex w-full items-center gap-3 transition-colors hover:bg-muted disabled:opacity-50"
                style={{
                  border: "1px solid var(--border)",
                  padding: "12px 16px",
                  fontSize: 14,
                }}
              >
                <GoogleIcon />
                <span className="flex-1 text-left">
                  {loading === "google" ? "Redirecting..." : "Continue with Google"}
                </span>
                <span
                  style={{
                    fontSize: 10,
                    letterSpacing: "0.1em",
                    color: "var(--muted-foreground)",
                  }}
                >
                  OAUTH
                </span>
              </button>
            </div>

            {/* Fine print */}
            <div className="mt-8 text-center" style={{ fontSize: 11, color: "var(--muted-foreground)" }}>
              <p>
                By signing in, you agree to our{" "}
                <Link href="/docs" className="underline underline-offset-2">
                  terms
                </Link>
                . We store your email and name only.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
