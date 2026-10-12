export type DocumentRecord = {
  id: string; filename: string; size_bytes: number; extension: string;
  state: "uploading" | "queued" | "processing" | "ready" | "failed" | "deleting";
  stage: string; error_code: string | null; unit_count: number; parser_version: string | null;
  chunk_count: number; embedded_count: number; index_version: string | null;
};
export type IndexedPassage = { ordinal: number; text: string; token_count: number; kind: string;
  start_number: number; end_number: number; start_offset: number; end_offset: number;
  start_unit: number; end_unit: number };
export type ExtractedUnit = { ordinal: number; kind: string; number: number; text: string };
const messages: Record<string, string> = {
  conversation_busy: "Un échange est déjà en cours dans cette conversation. Attendez sa fin.",
  conversation_unavailable: "Cette conversation n’est plus disponible.",
  generation_interrupted: "Le traitement a été interrompu. Aucun nouvel appel automatique n’est effectué.",
  request_conflict: "Cet identifiant d’envoi a déjà été utilisé avec une autre question.",
  conversation_quota: "La limite de 50 conversations est atteinte. Supprimez une conversation pour continuer.",
  conversation_message_quota: "Cette conversation a atteint 100 échanges. Ouvrez une nouvelle conversation.",
  external_processing_required: "Confirmez l’envoi à Groq pour générer une réponse.",
  llm_not_configured: "La génération Groq Free n’est pas configurée sur le serveur.",
  generation_busy: "Une réponse est déjà en cours. Réessayez après sa fin.",
  generation_quota: "La limite de génération est atteinte. Réessayez plus tard.",
  provider_quota: "Le quota Groq est atteint. Les appels sont suspendus ; réessayez plus tard.",
  generation_timeout: "La génération a dépassé le délai autorisé. Réessayez.",
  llm_unavailable: "Groq est temporairement indisponible. Réessayez plus tard.",
  context_budget: "La question ou les passages dépassent le budget. Raccourcissez la question ou choisissez d’autres documents.",
  invalid_citations: "La réponse contient une référence ou un extrait invalide et n’a pas été affichée.",
  invalid_llm_output: "La réponse reçue est incomplète ou invalide et n’a pas été affichée.",
  source_unavailable: "Une source a été supprimée ou modifiée pendant la réponse. Relancez la recherche.",
  selection_unavailable: "Un document sélectionné est indisponible. Actualisez la bibliothèque et choisissez à nouveau vos documents.",
  search_busy: "La recherche locale est occupée. Attendez la fin du traitement avant de réessayer.",
  search_timeout: "La recherche a dépassé le délai autorisé. Réessayez dans quelques instants.",
  search_unavailable: "La recherche est momentanément indisponible. Réessayez dans quelques instants.",
  query_too_long: "La question et son contexte dépassent la capacité du modèle. Raccourcissez votre question.",
  invalid_file: "Le fichier est corrompu ou son contenu ne correspond pas au format annoncé.",
  no_text: "Aucun texte exploitable. Les PDF scannés ne sont pas pris en charge.",
  invalid_encoding: "Le fichier TXT doit être encodé en UTF-8.",
  encrypted_file: "Les fichiers chiffrés ne sont pas pris en charge.",
  extraction_limit: "Le contenu dépasse les limites d’extraction du projet.",
  extraction_timeout: "L’extraction a dépassé le temps autorisé.",
  file_too_large: "La taille maximale est de 20 Mio par fichier.",
  storage_quota: "La bibliothèque a atteint son quota gratuit. Supprimez un document avant de continuer.",
  unsupported_format: "Choisissez un PDF textuel, un DOCX ou un TXT UTF-8.",
  upload_incomplete: "L’envoi du fichier n’est pas terminé.",
  size_mismatch: "La taille reçue ne correspond pas au fichier réservé.",
  not_found: "Ce document n’est plus disponible.",
  passage_quota: "Le quota gratuit de passages est atteint. Supprimez un document avant de relancer.",
  embedding_unavailable: "L’indexation est momentanément indisponible. Vous pouvez la relancer.",
  index_incompatible: "La version de l’index est incompatible. Une réindexation est nécessaire.",
  index_invalid: "Le contenu n’a pas pu être indexé dans les limites du projet.",
};
export function errorMessage(code: unknown): string {
  return typeof code === "string" && messages[code] ? messages[code] : "L’opération n’a pas abouti. Réessayez dans quelques instants.";
}
export async function documentRequest(path: string, method = "GET", data?: object): Promise<Response> {
  const response = await fetch(`/api/v1${path}`, {
    method, cache: "no-store", headers: data ? { "content-type": "application/json" } : undefined,
    body: data ? JSON.stringify(data) : undefined, signal: AbortSignal.timeout(15000),
  });
  if (response.status === 401) {
    window.dispatchEvent(new Event("session-expired"));
    throw new Error("Votre session a expiré. Reconnectez-vous.");
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(errorMessage(payload.code));
  }
  return response;
}
export function documentStatus(document: DocumentRecord): string {
  if (document.state === "processing" && (document.stage === "extracted" || document.stage === "indexing")) return "Indexation en cours";
  return { uploading: "Envoi en cours", queued: "En attente", processing: "Extraction en cours",
    ready: "Prêt", failed: document.stage === "indexing" ? "Indexation impossible" : "Extraction impossible", deleting: "Suppression en cours" }[document.state];
}
