/**
 * Database utilities for Neon Postgres.
 * Uses the native pg-compatible fetch driver via neon serverless.
 * Falls back to no-op in test/build environments where DATABASE_URL is unset.
 */

import { generateApiKey } from "./auth"

// ---- Migration SQL ----
export const MIGRATION_SQL = `
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  github_id TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL DEFAULT '',
  email TEXT NOT NULL DEFAULT '',
  api_key TEXT UNIQUE NOT NULL,
  tier TEXT NOT NULL DEFAULT 'free',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_github_id ON users(github_id);
CREATE INDEX IF NOT EXISTS idx_users_api_key ON users(api_key);

CREATE TABLE IF NOT EXISTS api_usage (
  id SERIAL PRIMARY KEY,
  api_key TEXT NOT NULL,
  endpoint TEXT NOT NULL,
  tokens_used INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_usage_api_key ON api_usage(api_key);
CREATE INDEX IF NOT EXISTS idx_api_usage_created_at ON api_usage(created_at);
`

// ---- Types ----
export interface User {
  id: number
  github_id: string
  name: string
  email: string
  api_key: string
  tier: string
  created_at: Date
}

export interface UsageRecord {
  id: number
  api_key: string
  endpoint: string
  tokens_used: number
  created_at: Date
}

// ---- Database Connection ----

/**
 * Execute a raw SQL query against Neon Postgres.
 * Uses fetch-based Neon serverless driver for edge compatibility.
 */
export async function query<T = Record<string, unknown>>(
  sql: string,
  params: unknown[] = [],
): Promise<T[]> {
  const databaseUrl = process.env.DATABASE_URL
  if (!databaseUrl) {
    console.warn("DATABASE_URL not set, skipping query")
    return []
  }

  // Use neon serverless HTTP query protocol with .query() for parameterized SQL
  const { neon } = await import("@neondatabase/serverless")
  const sql_fn = neon(databaseUrl)
  const result = await sql_fn.query(sql, params)
  return result as T[]
}

// ---- User Management ----

/**
 * Get or create a user by GitHub ID. Generates an API key on first login.
 */
export async function getOrCreateUser(
  githubId: string,
  name: string,
  email: string,
): Promise<User | null> {
  // Try to find existing user
  const existing = await query<User>(
    "SELECT * FROM users WHERE github_id = $1 LIMIT 1",
    [githubId],
  )

  if (existing.length > 0) {
    return existing[0]
  }

  // Create new user with a generated API key
  const apiKey = generateApiKey()
  const created = await query<User>(
    `INSERT INTO users (github_id, name, email, api_key, tier)
     VALUES ($1, $2, $3, $4, 'free')
     RETURNING *`,
    [githubId, name, email, apiKey],
  )

  return created[0] ?? null
}

/**
 * Look up a user by API key.
 */
export async function getUserByApiKey(apiKey: string): Promise<User | null> {
  if (!apiKey || !apiKey.startsWith("slm_")) {
    return null
  }

  const result = await query<User>(
    "SELECT * FROM users WHERE api_key = $1 LIMIT 1",
    [apiKey],
  )

  return result[0] ?? null
}

/**
 * Log an API usage record.
 */
export async function logUsage(
  apiKey: string,
  endpoint: string,
  tokensUsed: number,
): Promise<void> {
  await query(
    `INSERT INTO api_usage (api_key, endpoint, tokens_used)
     VALUES ($1, $2, $3)`,
    [apiKey, endpoint, tokensUsed],
  )
}

/**
 * Get usage stats for the last N days.
 */
export async function getUsageStats(
  apiKey: string,
  days: number = 7,
): Promise<{ date: string; requests: number; tokens: number }[]> {
  const result = await query<{
    date: string
    requests: string
    tokens: string
  }>(
    `SELECT
       DATE(created_at) as date,
       COUNT(*) as requests,
       COALESCE(SUM(tokens_used), 0) as tokens
     FROM api_usage
     WHERE api_key = $1
       AND created_at >= NOW() - INTERVAL '1 day' * $2
     GROUP BY DATE(created_at)
     ORDER BY date DESC`,
    [apiKey, days],
  )

  return result.map((r) => ({
    date: r.date,
    requests: parseInt(r.requests, 10),
    tokens: parseInt(r.tokens, 10),
  }))
}
