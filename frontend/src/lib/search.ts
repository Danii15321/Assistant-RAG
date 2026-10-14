import { type ModelChoice } from "@/lib/models";
import { errorMessage } from "@/lib/documents";

export type SearchHit = {
  document_id: string; generation: number; ordinal: number; filename: string; text: string;
  kind: string; start_number: number; end_number: number; score: number; token_count: number;
};
export type SearchResult = {
  status: "matches" | "no_match" | "empty_corpus"; hits: SearchHit[];
  threshold: number; top_k: number; context_tokens: number; elapsed_ms: number;
};
export async function searchDocuments(question: string, documentIds: string[] | null, signal: AbortSignal): Promise<SearchResult> {
  let response: Response;
  try { response = await fetch("/api/v1/search", {
    method: "POST", cache: "no-store", headers: { "content-type": "application/json" },
    body: JSON.stringify({ question, document_ids: documentIds }),
    signal: AbortSignal.any([signal, AbortSignal.timeout(120000)]),
  }); } catch (failure) {
    if (signal.aborted) throw failure;
    throw new Error(errorMessage(failure instanceof DOMException && failure.name === "TimeoutError" ? "search_timeout" : "search_unavailable"));
  }
  if (response.status === 401) {
    window.dispatchEvent(new Event("session-expired"));
    throw new Error("Votre session a expiré. Reconnectez-vous.");
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(errorMessage(payload.code));
  }
  return response.json();
}

export type AnswerResult = {
  model?: ModelChoice;
  state: "answered" | "insufficient_context"; answer: string;
  claims: { text: string; evidence: { source_id: string; quote: string }[] }[];
  sources: (Omit<SearchHit, "document_id"> & { document_id: string | null; source_id: string; status?: "available" | "deleted" })[]; provider_called: boolean;
};
export async function generateAnswer(question: string, documentIds: string[] | null, signal: AbortSignal, model: ModelChoice = "groq"): Promise<AnswerResult> {
  let response: Response;
  try { response = await fetch("/api/v1/answers", {
    method: "POST", cache: "no-store", headers: { "content-type": "application/json" },
    body: JSON.stringify({ question, document_ids: documentIds, allow_external_processing: true, model }),
    signal: AbortSignal.any([signal, AbortSignal.timeout(180000)]),
  }); } catch (failure) {
    if (signal.aborted) throw failure;
    throw new Error(errorMessage(failure instanceof DOMException && failure.name === "TimeoutError" ? "generation_timeout" : "llm_unavailable"));
  }
  if (response.status === 401) {
    window.dispatchEvent(new Event("session-expired"));
    throw new Error("Votre session a expiré. Reconnectez-vous.");
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(errorMessage(payload.code));
  }
  return response.json();
}
