import { errorMessage } from "@/lib/documents";
import { type AnswerResult } from "@/lib/search";

export type Conversation = { id: string; title: string; created_at: string; updated_at: string };
export type Exchange = { id: string; request_id: string; ordinal: number; question: string;
  document_ids: string[] | null; state: "pending" | "answered" | "insufficient_context" | "failed";
  answer: AnswerResult | null; error_code: string | null; created_at: string; completed_at: string | null };
export type MessageInput = { request_id: string; question: string; document_ids: string[] | null; allow_external_processing: boolean };

export function newRequestId(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, value => value.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export async function conversationRequest<T>(path: string, signal: AbortSignal, method = "GET", data?: MessageInput): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/v1/conversations${path}`, { method, cache: "no-store",
      headers: data ? { "content-type": "application/json" } : undefined,
      body: data ? JSON.stringify(data) : undefined,
      signal: AbortSignal.any([signal, AbortSignal.timeout(data ? 180000 : 15000)]),
    });
  } catch (failure) {
    if (signal.aborted) throw failure;
    throw new Error("La connexion a été interrompue. Vérifiez l’historique avant de renvoyer la question.");
  }
  if (response.status === 401) {
    window.dispatchEvent(new Event("session-expired"));
    throw new Error("Votre session a expiré. Reconnectez-vous.");
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(errorMessage(payload.code));
  }
  return response.status === 204 ? undefined as T : response.json();
}
