/**
 * Prisma client singleton with Neon serverless adapter.
 * Safe in edge + node runtimes, reuses connection across hot reloads in dev.
 */
import { PrismaClient } from "@prisma/client"
import { PrismaNeon } from "@prisma/adapter-neon"

const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient }

function createClient(): PrismaClient {
  const url = process.env.DATABASE_URL
  if (!url) {
    // Return a proxy that defers client creation until first use — avoids build-time errors
    return new Proxy({} as PrismaClient, {
      get(_, prop) {
        throw new Error(`DATABASE_URL not set — cannot access prisma.${String(prop)}`)
      },
    })
  }
  const adapter = new PrismaNeon({ connectionString: url })
  return new PrismaClient({ adapter })
}

export const prisma = globalForPrisma.prisma ?? createClient()

if (process.env.NODE_ENV !== "production") {
  globalForPrisma.prisma = prisma
}
