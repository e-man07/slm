"use client"

import * as React from "react"
import { signIn } from "next-auth/react"
import { Button } from "@/components/ui/button"

interface SignInButtonsProps {
  callbackUrl?: string
}

/** Inline SVG icons — no runtime dep on icon lib. */
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

export function SignInButtons({ callbackUrl = "/dashboard" }: SignInButtonsProps) {
  const [loading, setLoading] = React.useState<string | null>(null)

  const handle = async (provider: "github" | "google") => {
    setLoading(provider)
    try {
      await signIn(provider, { callbackUrl })
    } finally {
      // signIn redirects on success, so this runs only on error
      setLoading(null)
    }
  }

  return (
    <div className="space-y-3">
      <Button
        onClick={() => handle("github")}
        disabled={loading !== null}
        variant="outline"
        className="w-full justify-start gap-3 h-11"
      >
        <GitHubIcon />
        <span>{loading === "github" ? "Redirecting..." : "Continue with GitHub"}</span>
      </Button>

      <Button
        onClick={() => handle("google")}
        disabled={loading !== null}
        variant="outline"
        className="w-full justify-start gap-3 h-11"
      >
        <GoogleIcon />
        <span>{loading === "google" ? "Redirecting..." : "Continue with Google"}</span>
      </Button>
    </div>
  )
}
