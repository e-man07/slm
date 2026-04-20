import Link from "next/link"
import { redirect } from "next/navigation"
import { auth } from "@/lib/auth-next"
import { PageLayout } from "@/components/shared/page-layout"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { SignInButtons } from "@/components/auth/sign-in-buttons"

export const metadata = {
  title: "Sign in — Sealevel",
  description: "Sign in to Sealevel to access your API key, usage stats, and chat history.",
}

export default async function SignInPage({
  searchParams,
}: {
  searchParams: Promise<{ callbackUrl?: string }>
}) {
  const session = await auth()
  const { callbackUrl } = await searchParams

  // Already signed in — bounce to dashboard or callback
  if (session?.user) {
    redirect(callbackUrl ?? "/dashboard")
  }

  return (
    <PageLayout>
      <div className="mx-auto max-w-md py-8">
        <Card>
          <CardHeader className="space-y-2 text-center">
            <CardTitle className="text-2xl">Welcome to SLM</CardTitle>
            <CardDescription>
              Sign in to get your API key, track usage, and save chat history.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <SignInButtons callbackUrl={callbackUrl ?? "/dashboard"} />

            <div className="relative">
              <Separator />
              <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-card px-2 text-xs text-muted-foreground">
                OR
              </span>
            </div>

            <div className="space-y-2 text-center text-sm text-muted-foreground">
              <p>
                Use anonymously —{" "}
                <Link href="/chat" className="text-foreground underline underline-offset-2">
                  start chatting
                </Link>{" "}
                with 5 req/min limits.
              </p>
            </div>

            <p className="text-center text-xs text-muted-foreground">
              By signing in, you agree to our{" "}
              <Link href="/docs" className="underline underline-offset-2">
                terms
              </Link>
              . We store your email and name only.
            </p>
          </CardContent>
        </Card>
      </div>
    </PageLayout>
  )
}
