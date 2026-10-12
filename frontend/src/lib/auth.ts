import "server-only";
import { betterAuth } from "better-auth";
import { nextCookies } from "better-auth/next-js";
import { appURL } from "./app-url";
import { database } from "./database";
import { authOptions } from "./auth-options";

const baseURL = appURL();
const secret = process.env.BETTER_AUTH_SECRET;
if (!baseURL || !secret || !process.env.AUTH_DATABASE_URL) {
  throw new Error("Configuration de l’authentification manquante.");
}
const options = authOptions(database, baseURL, secret);
export const auth = betterAuth({ ...options, plugins: [...options.plugins, nextCookies()] });
