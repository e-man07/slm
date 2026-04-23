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
 * Get or create a user by OAuth provider + id.
 * API key is NOT generated on sign-up — user creates it on-demand from the dashboard.
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
      tier: "free",
    },
  })
}

/**
 * Generate an API key for a user who doesn't have one yet.
 */
export async function generateApiKeyForUser(userId: number) {
  const user = await prisma.user.findUnique({ where: { id: userId } })
  if (!user) return null
  if (user.apiKey) return user // already has one

  return prisma.user.update({
    where: { id: userId },
    data: { apiKey: generateApiKey() },
  })
}

/**
 * Rotate a user's API key — generates a new one, invalidates the old one.
 */
export async function rotateApiKey(userId: number) {
  return prisma.user.update({
    where: { id: userId },
    data: { apiKey: generateApiKey() },
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
 * Accepts userId (for web) and/or apiKey (for API). At least one required.
 */
export async function logUsage(
  identifier: { userId?: number | null; apiKey?: string | null },
  endpoint: string,
  tokensUsed: number,
  source: "web" | "api" = "api",
): Promise<void> {
  if (!identifier.userId && !identifier.apiKey) return
  await prisma.apiUsage.create({
    data: {
      userId: identifier.userId ?? null,
      apiKey: identifier.apiKey ?? null,
      endpoint,
      tokensUsed,
      source,
    },
  })
}

/**
 * Get today's token usage for a user (combined web + API).
 */
export async function getTodayTokensByUserId(userId: number): Promise<number> {
  const startOfDay = new Date()
  startOfDay.setUTCHours(0, 0, 0, 0)
  const result = await prisma.apiUsage.aggregate({
    where: { userId, createdAt: { gte: startOfDay } },
    _sum: { tokensUsed: true },
  })
  return result._sum.tokensUsed ?? 0
}

/**
 * Log a full prompt-response interaction for retraining data collection.
 */
export async function logInteraction(data: {
  userId: number | null
  source: string
  promptMessages: string
  response: string
  promptTokens?: number
  completionTokens?: number
  totalTokens?: number
  ragContext?: string | null
}): Promise<string | null> {
  if (!data.userId) return null
  const row = await prisma.interaction.create({
    data: {
      userId: data.userId,
      source: data.source,
      promptMessages: data.promptMessages,
      response: data.response,
      promptTokens: data.promptTokens ?? 0,
      completionTokens: data.completionTokens ?? 0,
      totalTokens: data.totalTokens ?? 0,
      ragContext: data.ragContext ?? null,
    },
  })
  return row.id
}

/**
 * Save feedback (thumbs up/down) for an interaction.
 */
export async function saveFeedback(interactionId: string, signal: "up" | "down") {
  return prisma.feedback.upsert({
    where: { interactionId },
    update: { signal },
    create: { interactionId, signal },
  })
}

/**
 * Get usage stats for the last N days, queried by userId.
 */
export async function getUsageStats(userId: number, days = 7) {
  const since = new Date(Date.now() - days * 86_400_000)
  const rows = await prisma.apiUsage.findMany({
    where: { userId, createdAt: { gte: since } },
    select: { createdAt: true, tokensUsed: true, endpoint: true, source: true },
  })

  const byDate = new Map<string, { requests: number; tokens: number }>()
  const byEndpoint = new Map<string, { requests: number; tokens: number }>()
  const bySource = new Map<string, { requests: number; tokens: number }>()

  for (const r of rows) {
    const date = r.createdAt.toISOString().slice(0, 10)
    const dateEntry = byDate.get(date) ?? { requests: 0, tokens: 0 }
    dateEntry.requests += 1
    dateEntry.tokens += r.tokensUsed
    byDate.set(date, dateEntry)

    const ep = r.endpoint
    const epEntry = byEndpoint.get(ep) ?? { requests: 0, tokens: 0 }
    epEntry.requests += 1
    epEntry.tokens += r.tokensUsed
    byEndpoint.set(ep, epEntry)

    const src = r.source
    const srcEntry = bySource.get(src) ?? { requests: 0, tokens: 0 }
    srcEntry.requests += 1
    srcEntry.tokens += r.tokensUsed
    bySource.set(src, srcEntry)
  }

  const daily = Array.from(byDate.entries())
    .map(([date, v]) => ({ date, ...v }))
    .sort((a, b) => a.date.localeCompare(b.date))

  const endpoints = Array.from(byEndpoint.entries())
    .map(([endpoint, v]) => ({ endpoint, ...v }))
    .sort((a, b) => b.tokens - a.tokens)

  const web = bySource.get("web") ?? { requests: 0, tokens: 0 }
  const api = bySource.get("api") ?? { requests: 0, tokens: 0 }

  return { daily, endpoints, web, api }
}

// ---- Chat Sessions ----

/**
 * List chat sessions for a user, most recent first.
 */
export async function listChatSessions(userId: number, source?: string) {
  return prisma.chatSession.findMany({
    where: { userId, ...(source ? { source } : {}) },
    orderBy: { updatedAt: "desc" },
    select: {
      id: true,
      title: true,
      source: true,
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
export async function createChatSession(userId: number | null, title = "New chat", source = "web") {
  return prisma.chatSession.create({
    data: { userId, title, source },
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
