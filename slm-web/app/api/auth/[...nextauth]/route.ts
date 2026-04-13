import NextAuth from "next-auth"
import { authConfig } from "@/lib/auth"

const handler = NextAuth(authConfig)

export const GET = handler.handlers.GET
export const POST = handler.handlers.POST
