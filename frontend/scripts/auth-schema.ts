import { writeFile } from "node:fs/promises";
import { getMigrations } from "better-auth/db/migration";
import { Pool } from "pg";
import { authOptions } from "../src/lib/auth-options";

const pool = new Pool({ connectionString: process.env.AUTH_DATABASE_URL, max: 1 });
try {
  const plan = await getMigrations(authOptions(pool, "http://localhost:3000", "schema-generation-only-not-a-runtime-secret-12345"));
  const sql = await plan.compileMigrations();
  await writeFile("../backend/migrations/sql/better-auth.generated.sql", "-- Better Auth 1.7.7 migration draft. Review before adding an Alembic revision.\n" + sql);
  console.log("SQL d’authentification généré pour relecture ; aucune migration exécutée.");
} finally { await pool.end(); }
