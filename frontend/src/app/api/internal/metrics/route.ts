import { authorizedInternal } from "@/lib/cloud";

export const dynamic = "force-dynamic";
export async function GET(request: Request) {
  if (!authorizedInternal(request)) return new Response(null, { status: 404 });
  try {
    const query = new URL(request.url).searchParams.get("probe") === "identity" ? "?probe=identity" : "";
    const response = await fetch(new URL("/internal/metrics" + query, process.env.API_INTERNAL_URL), {
      headers: { authorization: `Bearer ${process.env.INTERNAL_WORKER_SECRET}` },
      cache: "no-store", redirect: "error", signal: AbortSignal.timeout(query ? 30000 : 15000),
    });
    return new Response(await response.arrayBuffer(), { status: response.status,
      headers: { "content-type": "application/json", "cache-control": "no-store" } });
  } catch { return new Response(null, { status: 503 }); }
}
