import { authorizedInternal } from "@/lib/cloud";

export const dynamic = "force-dynamic";
export async function GET(request: Request) {
  if (!authorizedInternal(request)) return new Response(null, { status: 404 });
  try {
    const response = await fetch(`${process.env.API_INTERNAL_URL}/internal/metrics`, {
      headers: { authorization: `Bearer ${process.env.INTERNAL_WORKER_SECRET}` },
      cache: "no-store", redirect: "error", signal: AbortSignal.timeout(15000),
    });
    return new Response(await response.arrayBuffer(), { status: response.status,
      headers: { "content-type": "application/json", "cache-control": "no-store" } });
  } catch { return new Response(null, { status: 503 }); }
}
