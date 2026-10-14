"use client";

import { useRef, useState, type FormEvent } from "react";
import { ModelPicker } from "@/components/model-picker";
import { useModels, type ModelChoice } from "@/lib/models";
import { DocumentUpload } from "@/components/document-upload";
import { ChatIcon } from "@/components/chat-icon";
import { type DocumentRecord } from "@/lib/documents";

export function ConversationForm({ documents, busy, onSend, onUploaded, initialSelection = null, initialModel = "groq" }: {
  documents: DocumentRecord[]; busy: boolean; initialSelection?: string[] | null; initialModel?: ModelChoice;
  onUploaded: () => Promise<void>;
  onSend: (question: string, selection: string[] | null, model: ModelChoice) => Promise<boolean>;
}) {
  const [model, setModel] = useState<ModelChoice>(initialModel);
  const { catalog, error: modelError } = useModels(busy);
  const modelAvailable = catalog.models.some(item => item.id === model && item.available);
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState(initialSelection === null ? "all" : "selection");
  const [selection, setSelection] = useState<string[]>(initialSelection ?? []);
  const [consent, setConsent] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const submitting = useRef(false);
  const scope = useRef<HTMLDetailsElement>(null);
  const ready = documents.filter(document => document.state === "ready");
  const processing = documents.some(document => ["uploading", "queued", "processing"].includes(document.state));
  const unavailable = selection.some(id => !ready.some(document => document.id === id));
  const blocked = !modelAvailable || busy || uploading || processing || !ready.length || !consent || !question.trim() || (mode === "selection" && (!selection.length || unavailable));
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError("");
    if (blocked || submitting.current) return;
    submitting.current = true;
    if (scope.current) scope.current.open = false;
    try {
      if (await onSend(question.trim(), mode === "all" ? null : selection, model)) { setQuestion(""); setConsent(false); }
    } catch { setError("L’envoi a échoué. Votre question est conservée."); }
    finally { submitting.current = false; }
  }
  return <div className="composer-dock">
    <form className="chat-composer" onSubmit={event => void submit(event)}>
      <div className="composer-input">
      <DocumentUpload compact disabled={busy} onBusyChange={setUploading} onUploaded={onUploaded} />
      <label htmlFor="chat-question" className="visually-hidden">Votre question</label>
      <textarea id="chat-question" disabled={busy} required maxLength={1000} rows={1} value={question}
        placeholder="Posez votre question…" onChange={event => setQuestion(event.target.value)}
        onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); if (!blocked) event.currentTarget.form?.requestSubmit(); } }} />
      <button className="send-button" type="submit" disabled={blocked} aria-label="Envoyer ma question" title="Envoyer · Entrée"><ChatIcon name="arrow" /></button>
      </div>
      <div className="composer-toolbar">
        <ModelPicker catalog={catalog} model={model} disabled={busy} error={modelError} onChange={value => { setModel(value); setConsent(false); }} />
        <details ref={scope} className="scope-picker" onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) event.currentTarget.open = false; }} onKeyDown={event => { if (event.key === "Escape") { event.currentTarget.open = false; event.currentTarget.querySelector("summary")?.focus(); } }}><summary>Documents à consulter</summary><div className="scope-content">
          <label htmlFor="chat-scope">Périmètre de la réponse</label>
          <select id="chat-scope" disabled={busy} value={mode} onChange={event => setMode(event.target.value)}>
            <option value="all">Tous mes documents prêts</option><option value="selection">Choisir mes documents</option>
          </select>
          {mode === "selection" && <div className="search-selection">{ready.length ? ready.map(document =>
            <label key={document.id}><input type="checkbox" disabled={busy} checked={selection.includes(document.id)} onChange={event =>
              setSelection(old => event.target.checked ? [...old, document.id] : old.filter(id => id !== document.id))} />{document.filename}</label>) : <p>Aucun document prêt.</p>}</div>}
          {mode === "selection" && unavailable && <p role="alert">Un document sélectionné n’est plus disponible. Revenez à tous les documents ou modifiez la sélection.</p>}
        </div></details>
      <p className="composer-status" role="status">{uploading ? "Envoi des documents…" : processing ? "Préparation des documents… Vous pourrez envoyer votre question dès qu’ils seront prêts." : ready.length ? `${ready.length} document${ready.length > 1 ? "s" : ""} prêt${ready.length > 1 ? "s" : ""}` : "Ajoutez votre premier document avec le + · PDF, DOCX ou TXT, 20 Mio max."}{!processing && mode === "selection" && ` · ${selection.length} sélectionné(s)`}</p>
      </div>
      <label className="external-consent"><input type="checkbox" disabled={busy} checked={consent} onChange={event => setConsent(event.target.checked)} />J’accepte l’envoi à {model === "groq" ? "Groq" : "OpenAI"} de ma question, de l’historique utile et des extraits pour cette réponse.</label>

    </form>
    {documents.some(document => document.state === "failed") && <p className="form-error" role="status">Un document n’a pas pu être préparé. Consultez la bibliothèque pour le relancer.</p>}
    {error && <p className="form-error" role="alert">{error}</p>}
  </div>;
}
