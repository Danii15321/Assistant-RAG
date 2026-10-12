import { handleAuth } from "@/lib/auth-handler";
export const runtime = "nodejs";
export const GET = handleAuth;
export const POST = handleAuth;
