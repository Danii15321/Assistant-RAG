import "server-only";

export function appURL(): string {
  const url = process.env.APP_PUBLIC_URL ?? process.env.BETTER_AUTH_URL ??
    (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : undefined);
  if (!url) throw new Error("Application URL missing");
  return url;
}
