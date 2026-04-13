/**
 * Run database migrations against Neon Postgres.
 * Usage: bun scripts/migrate.ts
 */

import { MIGRATION_SQL, query } from "../lib/db"

async function main() {
  console.log("Running database migration...")
  console.log("SQL:\n", MIGRATION_SQL)

  try {
    // Split and run each statement individually since neon() may not handle multi-statement
    const statements = MIGRATION_SQL
      .split(";")
      .map((s) => s.trim())
      .filter((s) => s.length > 0)

    for (const stmt of statements) {
      await query(stmt + ";")
      console.log("  OK:", stmt.slice(0, 60) + "...")
    }

    console.log("\nMigration complete.")
  } catch (err) {
    console.error("Migration failed:", err)
    process.exit(1)
  }
}

main()
