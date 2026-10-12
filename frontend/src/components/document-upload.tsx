"use client";

import { useState, type FormEvent } from "react";
import { documentRequest, errorMessage } from "@/lib/documents";

type Props = { onUploaded: () => Promise<void> };
const types: Record<string, string> = { pdf: "application/pdf", txt: "text/plain",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" };

export function DocumentUpload({ onUploaded }: Props) {
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !files.length) return;
    setBusy(true); setError("");
    const form = event.currentTarget;
    try {
      for (const file of files) {
        const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
        if (!types[extension]) throw new Error(errorMessage("unsupported_format"));
        if (!file.size) throw new Error("Ce fichier est vide.");
        if (file.size > 20 * 1024 * 1024) throw new Error(errorMessage("file_too_large"));
        setProgress(`Envoi de ${file.name}…`);
        const reservation = await (await documentRequest("/documents/uploads", "POST", {
          filename: file.name, size_bytes: file.size, content_type: types[extension],
        })).json();
        try {
          // Short upload capability; no session cookie or JWT is sent to storage.
          const upload = await fetch(reservation.upload_url, { method: "PUT", body: file,
            headers: { ...(reservation.upload_token ? { authorization: `Bearer ${reservation.upload_token}` } : {}), "content-type": types[extension] },
            credentials: "omit", signal: AbortSignal.timeout(120000), redirect: "error" });
          if (!upload.ok) {
            const body = await upload.json().catch(() => ({}));
            throw new Error(errorMessage(body.code));
          }
          const finalized = await documentRequest("/documents", "POST", { upload_id: reservation.document.id });
          setProgress(finalized.status === 200 ? "Ce fichier est déjà dans votre bibliothèque." : "Fichier envoyé. Traitement lancé.");
          await onUploaded();
        } catch (failure) {
          await documentRequest(`/documents/${reservation.document.id}`, "DELETE").catch(() => undefined);
          throw failure;
        }
      }
      form.reset(); setFiles([]);
    } catch (failure) {
      setProgress(""); setError(failure instanceof Error ? failure.message : "L’envoi a échoué.");
      await onUploaded();
    } finally { setBusy(false); }
  }

  return <section className="upload-card" aria-labelledby="upload-title">
    <h2 id="upload-title">Importer des documents</h2>
    <p>PDF textuel, DOCX ou TXT UTF-8 · 20 Mio maximum par fichier.</p>
    <form onSubmit={submit}>
      <label htmlFor="documents">Choisir des fichiers</label>
      <input id="documents" type="file" accept=".pdf,.docx,.txt" multiple disabled={busy}
        onChange={event => { setFiles(Array.from(event.target.files ?? [])); setError(""); setProgress(""); }} />
      <button className="primary-button" type="submit" disabled={busy || files.length === 0}>
        {busy ? "Envoi en cours…" : "Importer"}</button>
    </form>
    {progress && <p role="status">{progress}</p>}
    {error && <p className="form-error" role="alert">{error}</p>}
    <p className="field-help">Stockage privé · Extraction côté serveur · Aucun envoi au LLM pendant l’import.</p>
  </section>;
}
