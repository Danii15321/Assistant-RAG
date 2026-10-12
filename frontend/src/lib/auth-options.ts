import type { BetterAuthOptions } from "better-auth";
import { jwt } from "better-auth/plugins/jwt";
import { username } from "better-auth/plugins/username";
import type { Pool } from "pg";

export const usernamePattern = /^[a-z0-9]+(?:-[a-z0-9]+)*\.[a-z0-9]+(?:-[a-z0-9]+)*$/;
export const normalizeUsername = (value: string) => value.trim().toLowerCase();

export function authOptions(database: Pool, baseURL: string, secret: string) {
  return {
    appName: "Assistant RAG", baseURL, secret, database,
    trustedOrigins: [new URL(baseURL).origin],
    emailAndPassword: { enabled: true, minPasswordLength: 12, maxPasswordLength: 128 },
    user: { modelName: "auth_user" },
    account: { modelName: "auth_account" },
    verification: { modelName: "auth_verification" },
    session: { modelName: "auth_session", expiresIn: 7 * 86400, updateAge: 86400,
               cookieCache: { enabled: false } },
    rateLimit: {
      enabled: true, storage: "database", modelName: "auth_rate_limit", window: 60, max: 120,
      customRules: {
        "/sign-up/email": { window: 60, max: 5 },
        "/sign-in/username": { window: 60, max: 10 },
      },
    },
    advanced: { ipAddress: { ipAddressHeaders: ["x-forwarded-for"] },
      defaultCookieAttributes: { httpOnly: true, sameSite: "lax", secure: baseURL.startsWith("https:") } },
    // Never log SDK errors containing database queries, credentials or request bodies.
    logger: { disabled: true },
    plugins: [
      username({ minUsernameLength: 3, maxUsernameLength: 64, displayUsername: false,
        immutableUsername: true, usernameNormalization: normalizeUsername,
        usernameValidator: (value) => usernamePattern.test(value),
        validationOrder: { username: "post-normalization" } }),
      jwt({ schema: { jwks: { modelName: "auth_jwks" } }, disableSettingJwtHeader: true,
        jwt: { issuer: baseURL, audience: "assistant-rag-api", expirationTime: "5m",
          definePayload: ({ session }) => ({ sid: session.id }) } }),
    ],
  } satisfies BetterAuthOptions;
}
