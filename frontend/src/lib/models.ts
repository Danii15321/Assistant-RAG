"use client";

import { useEffect, useState } from "react";
import { documentRequest } from "@/lib/documents";

export type ModelChoice = "groq" | "gpt-6-luna" | "gpt-6.1-sol";
export const modelLabels: Record<ModelChoice, string> = { groq: "Groq", "gpt-6-luna": "GPT-6 Luna", "gpt-6.1-sol": "GPT-6.1 Sol" };
export type ModelCatalog = { models: { id: ModelChoice; label: string; available: boolean; reason?: string }[]; remaining_microusd?: number; limit_microusd?: number };
const fallback: ModelCatalog = { models: [{ id: "groq", label: "Groq · gratuit", available: true }] };

export function useModels(busy: boolean) {
  const [catalog, setCatalog] = useState<ModelCatalog>(fallback);
  const [error, setError] = useState("");
  useEffect(() => {
    if (busy) return;
    const controller = new AbortController();
    documentRequest("/models", "GET", undefined, controller.signal)
      .then(response => response.json())
      .then((data: ModelCatalog) => { if (!controller.signal.aborted) { setCatalog(data); setError(""); } })
      .catch(() => { if (!controller.signal.aborted) { setCatalog(fallback); setError("Choix OpenAI indisponible. Vous pouvez utiliser Groq."); } });
    return () => controller.abort();
  }, [busy]);
  return { catalog, error };
}
