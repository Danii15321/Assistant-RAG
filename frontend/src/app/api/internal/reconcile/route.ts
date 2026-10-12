import { authorizedInternal, wakeWorker } from "@/lib/cloud";

export const dynamic = "force-dynamic";
export async function GET(request: Request) {
  if (!authorizedInternal(request, "CRON_SECRET")) return new Response(null, { status: 404 });
  await wakeWorker(true);
  return Response.json({ queued: true }, { headers: { "cache-control": "no-store" } });
}
