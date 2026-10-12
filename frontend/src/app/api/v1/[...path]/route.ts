import { auth } from "@/lib/auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const privateHeaders = { "cache-control": "no-store" };

async function forward(request: Request): Promise<Response> {
  const url = new URL(request.url);
  const health = url.pathname === "/api/v1/health" && request.method === "GET";
  const search = url.pathname === "/api/v1/search" && request.method === "POST";
  const answer = url.pathname === "/api/v1/answers" && request.method === "POST";
  const conversationMessage = /^\/api\/v1\/conversations\/[0-9a-fA-F-]+\/messages$/.test(url.pathname) && request.method === "POST";
  // File bytes always use the direct storage adapter; this bridge only accepts small JSON.
  if (url.pathname.startsWith("/api/v1/uploads/")) {
    return Response.json({ code: "not_found" }, { status: 404, headers: privateHeaders });
  }
  try {
    const headers = new Headers();
    if (!health) {
      const session = await auth.api.getSession({ headers: request.headers });
      if (!session) return Response.json({ detail: "Authentication required" }, {
        status: 401, headers: privateHeaders,
      });
      if (request.method !== "GET" && request.headers.get("origin") !== new URL(process.env.BETTER_AUTH_URL!).origin) {
        return Response.json({ code: "invalid_origin" }, { status: 403, headers: privateHeaders });
      }
      const { token } = await auth.api.getToken({ headers: request.headers });
      headers.set("authorization", `Bearer ${token}`);
    }
    let body: string | undefined;
    if (request.method === "POST") {
      const reader = request.body?.getReader();
      const chunks: Uint8Array[] = [];
      let size = 0;
      if (reader) {
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          size += value.byteLength;
          if (size > (search || answer || conversationMessage ? 16384 : 4096)) {
            await reader.cancel();
            return Response.json({ code: "request_too_large" }, { status: 413, headers: privateHeaders });
          }
          chunks.push(value);
        }
      }
      body = Buffer.concat(chunks).toString("utf8");
      headers.set("content-type", "application/json");
    }
    const upstream = await fetch(`${process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000"}${url.pathname}${url.search}`, {
      method: request.method, body, headers, cache: "no-store", redirect: "error", signal: AbortSignal.timeout(answer || conversationMessage ? 175000 : search ? 115000 : 6000),
    });
    return new Response(upstream.status === 204 ? null : await upstream.arrayBuffer(), { status: upstream.status,
      headers: { "content-type": "application/json", ...privateHeaders } });
  } catch {
    return Response.json({ code: "service_unavailable" }, { status: 503, headers: privateHeaders });
  }
}

export const GET = forward;
export const POST = forward;
export const DELETE = forward;
