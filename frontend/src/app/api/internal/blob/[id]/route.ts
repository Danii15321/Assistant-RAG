import { del, issueSignedToken, list, presignUrl } from "@vercel/blob";
import { authorizedInternal, uuidPattern } from "@/lib/cloud";

export const dynamic = "force-dynamic";
const headers = { "cache-control": "no-store" };
type Context = { params: Promise<{ id: string }> };
async function handle(request: Request, context: Context) {
  if (!authorizedInternal(request)) return new Response(null, { status: 404, headers });
  const { id } = await context.params;
  try {
    if (id === "reconcile" && request.method === "POST") {
      const raw = await request.text();
      if (raw.length > 10000) return new Response(null, { status: 413, headers });
      const input: unknown = JSON.parse(raw);
      const live = input && typeof input === "object" && "live" in input ? input.live : null;
      if (!Array.isArray(live) || live.length > 100 || !live.every(x => typeof x === "string" && uuidPattern.test(x))) return new Response(null, { status: 400, headers });
      const kept = new Set(live);
      let removed = 0, cursor: string | undefined;
      for (let page = 0; page < 20; page++) {
        const result = await list({ limit: 1000, cursor });
        const stale = result.blobs.filter(blob => uuidPattern.test(blob.pathname) && !kept.has(blob.pathname) && blob.uploadedAt.getTime() < Date.now() - 3600000);
        if (stale.length) await del(stale.map(blob => blob.pathname));
        removed += stale.length;
        if (!result.hasMore) break;
        cursor = result.cursor;
      }
      return Response.json({ removed }, { headers });
    }
    if (!uuidPattern.test(id)) return new Response(null, { status: 404, headers });
    if (request.method === "DELETE") { await del(id); return new Response(null, { status: 204, headers }); }
    if (request.method !== "GET") return new Response(null, { status: 405, headers });
    const signed = await issueSignedToken({ pathname: id, operations: ["get"], validUntil: Date.now() + 120000 });
    const { presignedUrl } = await presignUrl(signed, { pathname: id, operation: "get", access: "private", useCache: false });
    return Response.json({ url: presignedUrl }, { headers });
  } catch { return Response.json({ code: "storage_unavailable" }, { status: 503, headers }); }
}
export const GET = handle;
export const DELETE = handle;
export const POST = handle;
