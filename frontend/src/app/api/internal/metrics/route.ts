import { authorizedInternal } from "@/lib/cloud";

export const dynamic = "force-dynamic";
export async function GET(request: Request) {
  if (!authorizedInternal(request)) return new Response(null, { status: 404 });
  try {
    const probe = new URL(request.url).searchParams.get("probe");
    const query = probe === "identity" || probe === "embedding" ? "?probe=" + probe : "";
    const response = await fetch(new URL("/internal/metrics" + query, process.env.API_INTERNAL_URL), {
      headers: { authorization: `Bearer ${process.env.INTERNAL_WORKER_SECRET}` },
      cache: "no-store", redirect: "error", signal: AbortSignal.timeout(probe === "embedding" ? 150000 : query ? 30000 : 15000),
    });
    return new Response(await response.arrayBuffer(), { status: response.status,
      headers: { "content-type": "application/json", "cache-control": "no-store" } });
  } catch { return new Response(null, { status: 503 }); }
}
