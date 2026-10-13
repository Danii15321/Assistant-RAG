"use client";

import { useId, useRef, useState, type FormEvent } from "react";
import { ChatIcon } from "@/components/chat-icon";
import { documentRequest, errorMessage } from "@/lib/documents";

type Props = { onUploaded: () => Promise<void>; compact?: boolean; disabled?: boolean; onBusyChange?: (busy: boolean) => void };
const types: Record<string, string> = { pdf: "application/pdf", txt: "text/plain",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" };

export function DocumentUpload({ onUploaded, compact = false, disabled = false, onBusyChange }: Props) {
  const inputId = useId();
  const input = useRef<HTMLInputElement>(null);
  const running = useRef(false);
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [progress, setProgress] = useState("");
  const [results, setResults] = useState<string[]>([]);

  async function upload(batch: File[]) {
    if (running.current || disabled || !batch.length) return;
    running.current = true; setBusy(true); onBusyChange?.(true);
    setErrors([]); setResults([]); setProgress("");
    try {
      for (const [index, file] of batch.entries()) {
        try {
          const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
          if (!types[extension]) throw new Error(errorMessage("unsupported_format"));
          if (!file.size) throw new Error("Ce fichier est vide.");
          if (file.size > 20 * 1024 * 1024) throw new Error(errorMessage("file_too_large"));
          setProgress(`Envoi de ${file.name} (${index + 1}/${batch.length})…`);
          const reservation = await (await documentRequest("/documents/uploads", "POST", {
            filename: file.name, size_bytes: file.size, content_type: types[extension],
          })).json();
          let message: string;
          try {
            // Only the short storage capability is sent; never application cookies.
            const response = await fetch(reservation.upload_url, { method: "PUT", body: file,
              headers: { ...(reservation.upload_token ? { authorization: `Bearer ${reservation.upload_token}` } : {}), "content-type": types[extension] },
              credentials: "omit", signal: AbortSignal.timeout(120000), redirect: "error" });
            if (!response.ok) {
              const body = await response.json().catch(() => ({}));
              throw new Error(errorMessage(body.code));
            }
            const finalized = await documentRequest("/documents", "POST", { upload_id: reservation.document.id });
            message = finalized.status === 200 ? "Ce fichier est déjà dans votre bibliothèque." : "Fichier envoyé. Traitement lancé.";
          } catch (failure) {
            await documentRequest(`/documents/${reservation.document.id}`, "DELETE").catch(() => undefined);
            throw failure;
          }
          setProgress(message);
          setResults(previous => [...previous, `${file.name} · ${message}`]);
          // A refresh failure must never delete a successfully finalized original.
          await onUploaded();
        } catch (failure) {
          setErrors(previous => [...previous, `${file.name} : ${failure instanceof Error ? failure.message : "L’envoi a échoué."}`]);
        }
      }
      if (input.current) input.current.value = "";
      setFiles([]);
    } finally { running.current = false; setBusy(false); onBusyChange?.(false); }
  }
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); void upload(files); }
  const picker = <input ref={input} id={inputId} type="file" accept=".pdf,.docx,.txt" multiple disabled={busy || disabled}
    className={compact ? "visually-hidden" : undefined} tabIndex={compact ? -1 : undefined} aria-label="Choisir des fichiers"
    onChange={event => { const batch = Array.from(event.target.files ?? []); setFiles(batch); if (compact) void upload(batch); else { setErrors([]); setProgress(""); setResults([]); } }} />;
  const feedback = <div className="upload-feedback">
    {progress && <p role="status">{progress}</p>}
    {compact && results.length > 0 && <ul aria-label="Documents ajoutés">{results.map((result, index) => <li key={index}>{result}</li>)}</ul>}
    {errors.length > 0 && <div className="form-error" role="alert">{errors.map((error, index) => <p key={index}>{error}</p>)}</div>}
  </div>;
  if (compact) return <div className="composer-upload">
    {picker}<button type="button" className="icon-button attach-button" aria-label="Ajouter des documents" title="Ajouter des documents · PDF, DOCX, TXT · 20 Mio max." disabled={busy || disabled} onClick={() => input.current?.click()}><ChatIcon name="plus" /></button>
    {feedback}
  </div>;
  return <section className="upload-card" aria-labelledby="upload-title">
    <h2 id="upload-title">Importer des documents</h2>
    <p>PDF textuel, DOCX ou TXT UTF-8 · 20 Mio maximum par fichier.</p>
    <form onSubmit={submit}><label htmlFor={inputId}>Choisir des fichiers</label>{picker}
      <button className="primary-button" type="submit" disabled={busy || files.length === 0}>{busy ? "Envoi en cours…" : "Importer"}</button>
    </form>{feedback}
    <p className="field-help">Vos fichiers restent privés. L’import ne les envoie pas à Groq.</p>
  </section>;
}
