import { appURL } from "@/lib/app-url";
import { auth } from "@/lib/auth";
import { cloudEnabled, uploadCapability, wakeWorker } from "@/lib/cloud";

export const maxDuration = 300;
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
      if (request.method !== "GET" && request.headers.get("origin") !== new URL(appURL()).origin) {
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
    const upstream = await fetch(new URL(url.pathname + url.search, process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000"), {
      method: request.method, body, headers, cache: "no-store", redirect: "error", signal: AbortSignal.timeout(answer || conversationMessage ? 175000 : search ? 115000 : cloudEnabled() ? 60000 : 6000),
    });
    const bytes = upstream.status === 204 ? null : await upstream.arrayBuffer();
    if (cloudEnabled() && upstream.ok && url.pathname.startsWith("/api/v1/documents")) {
      if (url.pathname === "/api/v1/documents/uploads" && request.method === "POST") {
        const reservation = JSON.parse(Buffer.from(bytes!).toString("utf8"));
        return Response.json(await uploadCapability(reservation.document), { status: upstream.status, headers: privateHeaders });
      }
      if (request.method !== "GET" || (bytes && /"state":"(?:queued|processing|deleting)"/.test(Buffer.from(bytes).toString("utf8")))) await wakeWorker();
    }
    return new Response(bytes, { status: upstream.status,
      headers: { "content-type": "application/json", ...privateHeaders } });
  } catch (error) {
    // Log only bounded error categories, never URLs, tokens or request content.
    const category = error instanceof Error ? error.name : "UnknownError";
    const cause = error instanceof Error && error.cause && typeof error.cause === "object" && "code" in error.cause ? String(error.cause.code) : "unknown";
    console.error("API bridge failed", {
      category: /^[A-Za-z]{1,40}$/.test(category) ? category : "Error",
      cause: /^[A-Z_0-9]{1,40}$/.test(cause) ? cause : "unknown",
      bindingConfigured: !!process.env.API_INTERNAL_URL,
      redirectRejected: error instanceof Error && error.cause instanceof Error && /redirect/i.test(error.cause.message),
    });
    return Response.json({ code: "service_unavailable" }, { status: 503, headers: privateHeaders });
  }
}

export const GET = forward;
export const POST = forward;
export const DELETE = forward;
