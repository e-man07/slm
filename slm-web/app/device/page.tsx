"use client"

import * as React from "react"
import { signIn, useSession } from "next-auth/react"
import { NavBar } from "@/components/nav-bar"

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

export default function DevicePage() {
  const { data: session, status } = useSession()
  const [code, setCode] = React.useState("")
  const [step, setStep] = React.useState<"enter" | "verifying" | "done" | "error">("enter")
  const [errorMsg, setErrorMsg] = React.useState("")

  // Auto-fill code from URL query param
  React.useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const urlCode = params.get("code")
    if (urlCode) setCode(urlCode)
  }, [])

  const handleVerify = async () => {
    if (!code.trim()) return
    setStep("verifying")

    try {
      const res = await fetch("/api/auth/device/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: code.trim().toUpperCase() }),
      })
      if (res.ok) {
        setStep("done")
      } else {
        const data = await res.json()
        setErrorMsg(data.error?.message ?? "Verification failed")
        setStep("error")
      }
    } catch {
      setErrorMsg("Network error — try again")
      setStep("error")
    }
  }

  const isAuthed = status === "authenticated" && session?.user

  return (
    <div className="flex min-h-svh flex-col">
      <NavBar minimal />

      <div
        className="flex flex-1 items-center justify-center"
        style={{ borderTop: "1px solid var(--border)", padding: "60px 24px" }}
      >
        <div style={{ width: "100%", maxWidth: 480 }}>
          {/* Header */}
          <div
            style={{
              fontSize: 10,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              color: "var(--slm-accent)",
              fontWeight: 600,
            }}
          >
            SEALEVEL CLI / DEVICE LOGIN
          </div>

          <h1 className="mt-4 font-bold" style={{ fontSize: 28 }}>
            Authorize your CLI.
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Enter the code shown in your terminal to link your account.
          </p>

          {/* Step 1: Not logged in — show OAuth buttons */}
          {!isAuthed && status !== "loading" && (
            <div className="mt-8">
              <p className="mb-4 text-sm text-muted-foreground">
                First, sign in to your Sealevel account:
              </p>
              <div className="flex flex-col gap-3">
                <button
                  onClick={() => signIn("github", { callbackUrl: window.location.href })}
                  className="flex w-full items-center gap-3 transition-colors hover:bg-muted"
                  style={{
                    border: "1px solid var(--border)",
                    padding: "12px 16px",
                    fontSize: 14,
                  }}
                >
                  <GitHubIcon />
                  <span className="flex-1 text-left">Continue with GitHub</span>
                </button>
                <button
                  onClick={() => signIn("google", { callbackUrl: window.location.href })}
                  className="flex w-full items-center gap-3 transition-colors hover:bg-muted"
                  style={{
                    border: "1px solid var(--border)",
                    padding: "12px 16px",
                    fontSize: 14,
                  }}
                >
                  <GoogleIcon />
                  <span className="flex-1 text-left">Continue with Google</span>
                </button>
              </div>
            </div>
          )}

          {/* Step 2: Logged in — show code input */}
          {isAuthed && step === "enter" && (
            <div className="mt-8">
              <p className="mb-4 text-sm text-muted-foreground">
                Signed in as <strong>{session.user?.name ?? session.user?.email}</strong>
              </p>

              <label
                htmlFor="device-code"
                style={{
                  display: "block",
                  fontSize: 10,
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                  color: "var(--muted-foreground)",
                  marginBottom: 8,
                }}
              >
                Device Code
              </label>
              <input
                id="device-code"
                type="text"
                value={code}
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                placeholder="XXXX-XXXX"
                aria-label="Device code"
                name="deviceCode"
                autoComplete="one-time-code"
                spellCheck={false}
                maxLength={9}
                className="w-full text-center font-mono text-2xl tracking-[0.2em] border border-border bg-transparent p-4 outline-none focus-visible:border-[var(--slm-accent)]"
              />

              <button
                onClick={handleVerify}
                disabled={code.trim().length < 9}
                className="mt-4 flex w-full items-center justify-center gap-2 font-medium transition-opacity hover:opacity-90 disabled:opacity-50"
                style={{
                  background: "var(--slm-accent)",
                  color: "oklch(0.153 0.006 107.1)",
                  padding: "12px 0",
                  fontSize: 14,
                }}
              >
                Authorize CLI
              </button>
            </div>
          )}

          {/* Verifying */}
          {step === "verifying" && (
            <div className="mt-8 text-center">
              <p className="text-muted-foreground">Verifying...</p>
            </div>
          )}

          {/* Done */}
          {step === "done" && (
            <div className="mt-8" style={{ border: "1px solid var(--slm-accent)", padding: 24 }}>
              <p style={{ color: "var(--slm-accent)", fontWeight: 600 }}>
                ✓ CLI authorized successfully
              </p>
              <p className="mt-2 text-sm text-muted-foreground">
                You can close this tab. Your CLI is now connected.
              </p>
            </div>
          )}

          {/* Error */}
          {step === "error" && (
            <div className="mt-8">
              <div style={{ border: "1px solid var(--destructive)", padding: 24 }}>
                <p style={{ color: "var(--destructive)", fontWeight: 600 }}>
                  ✗ {errorMsg}
                </p>
              </div>
              <button
                onClick={() => { setStep("enter"); setErrorMsg("") }}
                className="mt-4 text-sm underline underline-offset-2 text-muted-foreground"
              >
                Try again
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
