import { randomUUID } from "crypto"
import GitHub from "next-auth/providers/github"
import type { NextAuthConfig } from "next-auth"

/**
 * Generate a random API key with `slm_` prefix.
 * Uses crypto.randomUUID for sufficient entropy.
 */
export function generateApiKey(): string {
  return `slm_${randomUUID().replace(/-/g, "")}`
}

export const authConfig: NextAuthConfig = {
  providers: [
    GitHub({
      clientId: process.env.GITHUB_CLIENT_ID,
      clientSecret: process.env.GITHUB_CLIENT_SECRET,
    }),
  ],
  session: {
    strategy: "jwt" as const,
  },
  callbacks: {
    async jwt({ token, account, profile }) {
      if (account && profile) {
        token.githubId = String(
          (profile as Record<string, unknown>).id ?? account.providerAccountId,
        )
        token.name = (profile.name as string) ?? ""
        token.email = (profile.email as string) ?? ""
      }
      return token
    },
    async session({ session, token }) {
      if (session.user && token.githubId) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        ;(session.user as any).githubId = token.githubId
      }
      return session
    },
  },
  pages: {
    signIn: "/dashboard",
  },
}
