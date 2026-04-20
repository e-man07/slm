/**
 * Database layer — Prisma + Neon Postgres.
 * Users, API usage tracking, and chat session persistence.
 */
import { generateApiKey } from "./auth"
import { prisma } from "./prisma"

// ---- Types (re-exported from Prisma for convenience) ----
export type { User, ApiUsage, ChatSession, ChatMessage } from "@prisma/client"

// ---- User Management ----

/**
 * Get or create a user by OAuth provider + id. Generates an API key on first login.
 */
export async function getOrCreateUser(
  provider: "github" | "google",
  providerId: string,
  name: string,
  email: string,
) {
  const existing = await prisma.user.findUnique({
    where: { provider_providerId: { provider, providerId } },
  })
  if (existing) return existing

  return prisma.user.create({
    data: {
      provider,
      providerId,
      name,
      email,
      apiKey: generateApiKey(),
      tier: "free",
    },
  })
}

/**
 * Look up a user by API key.
 */
export async function getUserByApiKey(apiKey: string) {
  if (!apiKey || !apiKey.startsWith("slm_")) return null
  return prisma.user.findUnique({ where: { apiKey } })
}

/**
 * Log an API usage record.
 */
export async function logUsage(
  apiKey: string,
  endpoint: string,
  tokensUsed: number,
): Promise<void> {
  await prisma.apiUsage.create({
    data: { apiKey, endpoint, tokensUsed },
  })
}

/**
 * Get usage stats for the last N days.
 */
export async function getUsageStats(apiKey: string, days = 7) {
  const since = new Date(Date.now() - days * 86_400_000)
  const rows = await prisma.apiUsage.findMany({
    where: { apiKey, createdAt: { gte: since } },
    select: { createdAt: true, tokensUsed: true },
  })

  const byDate = new Map<string, { requests: number; tokens: number }>()
  for (const r of rows) {
    const date = r.createdAt.toISOString().slice(0, 10)
    const entry = byDate.get(date) ?? { requests: 0, tokens: 0 }
    entry.requests += 1
    entry.tokens += r.tokensUsed
    byDate.set(date, entry)
  }

  return Array.from(byDate.entries())
    .map(([date, v]) => ({ date, ...v }))
    .sort((a, b) => b.date.localeCompare(a.date))
}

// ---- Chat Sessions ----

/**
 * List chat sessions for a user, most recent first.
 */
export async function listChatSessions(userId: number) {
  return prisma.chatSession.findMany({
    where: { userId },
    orderBy: { updatedAt: "desc" },
    select: {
      id: true,
      title: true,
      createdAt: true,
      updatedAt: true,
      _count: { select: { messages: true } },
    },
  })
}

/**
 * Get a chat session with all its messages.
 */
export async function getChatSession(sessionId: string, userId?: number) {
  const session = await prisma.chatSession.findUnique({
    where: { id: sessionId },
    include: { messages: { orderBy: { createdAt: "asc" } } },
  })
  if (!session) return null
  // Ownership check — if userId provided, must match
  if (userId !== undefined && session.userId !== userId) return null
  return session
}

/**
 * Create a new chat session.
 */
export async function createChatSession(userId: number | null, title = "New chat") {
  return prisma.chatSession.create({
    data: { userId, title },
  })
}

/**
 * Append a message to a session. Updates session.updatedAt.
 */
export async function addChatMessage(
  sessionId: string,
  role: "user" | "assistant" | "system",
  content: string,
) {
  const [message] = await prisma.$transaction([
    prisma.chatMessage.create({
      data: { sessionId, role, content },
    }),
    prisma.chatSession.update({
      where: { id: sessionId },
      data: { updatedAt: new Date() },
    }),
  ])
  return message
}

/**
 * Rename or delete a session.
 */
export async function updateChatSession(
  sessionId: string,
  userId: number,
  title: string,
) {
  return prisma.chatSession.updateMany({
    where: { id: sessionId, userId },
    data: { title },
  })
}

export async function deleteChatSession(sessionId: string, userId: number) {
  return prisma.chatSession.deleteMany({
    where: { id: sessionId, userId },
  })
}
