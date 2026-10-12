import "server-only";
import { timingSafeEqual } from "node:crypto";
import { issueSignedToken, presignUrl } from "@vercel/blob";
import { QueueClient } from "@vercel/queue";
import { database } from "./database";

export const cloudEnabled = () => process.env.CLOUD_RUNTIME === "true";
export const cloudQueue = new QueueClient({ region: "fra1" });
export const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
export function authorizedInternal(request: Request, variable = "INTERNAL_WORKER_SECRET") {
  const secret = process.env[variable];
  const supplied = Buffer.from(request.headers.get("authorization") ?? "");
  const expected = Buffer.from(`Bearer ${secret ?? ""}`);
  return cloudEnabled() && !!secret && supplied.length === expected.length && timingSafeEqual(supplied, expected);
}

export async function uploadCapability(document: { id: string; extension: string; size_bytes: number }) {
  if (!uuidPattern.test(document.id) || !Number.isInteger(document.size_bytes) || document.size_bytes < 1 || document.size_bytes > 20 * 1024 * 1024) throw new Error("Invalid reservation");
  const contentType = ({ txt: "text/plain", pdf: "application/pdf", docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" } as Record<string, string>)[document.extension];
  if (!contentType) throw new Error("Invalid format");
  const constraints = { pathname: document.id, validUntil: Date.now() + 9 * 60 * 1000,
    allowedContentTypes: [contentType], maximumSizeInBytes: document.size_bytes };
  const signed = await issueSignedToken({ ...constraints, operations: ["put"] });
  const { presignedUrl } = await presignUrl(signed, { ...constraints, operation: "put", access: "private",
    addRandomSuffix: false, allowOverwrite: false, cacheControlMaxAge: 60 });
  return { document, upload_url: presignedUrl, upload_token: null, expires_in: 540 };
}

export async function wakeWorker(reconcile = false): Promise<void> {
  if (!cloudEnabled()) return;
  // Shared throttle. Durable SQL jobs survive an interrupted enqueue; polling and cron re-send.
  const lease = await database.query("UPDATE cloud_wakeups SET next_at=now()+interval '15 seconds' WHERE id=1 AND next_at<=now() RETURNING id");
  if (!lease.rowCount && !reconcile) return;
  try {
    await cloudQueue.send("ingestion", { reconcile }, { retentionSeconds: 604800 });
  } catch {
    await database.query("UPDATE cloud_wakeups SET next_at=now() WHERE id=1");
    // Do not undo a committed import or encourage sending its bytes twice.
    console.warn("Worker notification unavailable; durable jobs await reconciliation");
  }
}

export async function runWorker(reconcile: boolean): Promise<void> {
  const response = await fetch(`${process.env.API_INTERNAL_URL}/internal/work`, {
    method: "POST", headers: { authorization: `Bearer ${process.env.INTERNAL_WORKER_SECRET}`,
      "x-reconcile": reconcile ? "1" : "0" }, cache: "no-store", redirect: "error",
    signal: AbortSignal.timeout(250000),
  });
  if (!response.ok || (await response.json()).pending) throw new Error("Durable work remains");
}
