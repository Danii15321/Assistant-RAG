import "server-only";
import { Pool } from "pg";

export const database = new Pool({ connectionString: process.env.AUTH_DATABASE_URL,
  max: 5, connectionTimeoutMillis: 10000, idleTimeoutMillis: 30000 });
