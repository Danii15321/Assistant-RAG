import { cloudQueue, runWorker } from "@/lib/cloud";

export const maxDuration = 300;
const callback = cloudQueue.handleCallback(async (message: { reconcile?: boolean }) => {
  await runWorker(message.reconcile === true);
}, { retry: (_error, metadata) => metadata.deliveryCount >= 100
  ? { acknowledge: true } : { afterSeconds: 15 }, visibilityTimeoutSeconds: 300 });

export async function POST(request: Request) { return callback(request); }
