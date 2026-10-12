import "server-only";
import { betterAuth } from "better-auth";
import { nextCookies } from "better-auth/next-js";
import { Pool } from "pg";
import { authOptions } from "./auth-options";

const database = new Pool({ connectionString: process.env.AUTH_DATABASE_URL, max: 5,
  connectionTimeoutMillis: 3000, idleTimeoutMillis: 30000 });
const baseURL = process.env.BETTER_AUTH_URL;
const secret = process.env.BETTER_AUTH_SECRET;
if (!baseURL || !secret || !process.env.AUTH_DATABASE_URL) {
  throw new Error("Configuration locale de l’authentification manquante.");
}
const options = authOptions(database, baseURL, secret);
export const auth = betterAuth({ ...options, plugins: [...options.plugins, nextCookies()] });
