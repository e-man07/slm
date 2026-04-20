import { randomUUID } from "crypto"
import GitHub from "next-auth/providers/github"
import Google from "next-auth/providers/google"
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
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
    }),
  ],
  session: {
    strategy: "jwt" as const,
  },
  callbacks: {
    async jwt({ token, account, profile }) {
      if (account && profile) {
        const provider =
          account.provider === "google" ? "google" : "github"
        // GitHub: profile.id. Google: profile.sub. Fallback: providerAccountId.
        const providerId = String(
          (profile as Record<string, unknown>).sub ??
            (profile as Record<string, unknown>).id ??
            account.providerAccountId,
        )
        const name = (profile.name as string) ?? ""
        const email = (profile.email as string) ?? ""
        token.provider = provider
        token.providerId = providerId
        token.name = name
        token.email = email

        // Create or fetch user in DB
        try {
          const { getOrCreateUser } = await import("./db")
          const user = await getOrCreateUser(provider, providerId, name, email)
          if (user) {
            token.userId = user.id
            token.apiKey = user.apiKey
            token.tier = user.tier
          }
        } catch (err) {
          console.warn("getOrCreateUser failed", err)
        }
      }
      return token
    },
    async session({ session, token }) {
      if (session.user) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const u = session.user as any
        u.provider = token.provider
        u.providerId = token.providerId
        u.userId = token.userId
        u.apiKey = token.apiKey
        u.tier = token.tier
      }
      return session
    },
  },
  pages: {
    signIn: "/sign-in",
  },
}
