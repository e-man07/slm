/**
 * NextAuth instance — created once, exposes `auth()`, `handlers`, `signIn`, `signOut`.
 * Use `auth()` in server components/route handlers to get the current session.
 */
import NextAuth from "next-auth"
import { authConfig } from "./auth"

export const { auth, handlers, signIn, signOut } = NextAuth(authConfig)
