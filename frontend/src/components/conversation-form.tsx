"use client";

import { useState, type FormEvent } from "react";
import { type DocumentRecord } from "@/lib/documents";

export function ConversationForm({ documents, busy, onSend, initialSelection = null }: {
  documents: DocumentRecord[]; busy: boolean; initialSelection?: string[] | null;
  onSend: (question: string, selection: string[] | null) => Promise<boolean>;
}) {
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState(initialSelection === null ? "all" : "selection");
  const [selection, setSelection] = useState<string[]>(initialSelection ?? []);
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError("");
    if (busy || !consent || !question.trim()) return;
    if (mode === "selection" && !selection.length) { setError("Choisissez au moins un document."); return; }
    if (await onSend(question, mode === "all" ? null : selection)) { setQuestion(""); setConsent(false); }
  }
  return <section className="document-list" aria-labelledby="conversation-form-title">
    <h2 id="conversation-form-title">Poursuivre la conversation</h2>
    <p>Posez une question ou un suivi. Les passages sont recherchés à nouveau pour chaque échange.</p>
    <form className="search-form" onSubmit={event => void submit(event)}>
      <fieldset disabled={busy}><label htmlFor="chat-question">Votre question</label>
        <textarea id="chat-question" required maxLength={1000} rows={3} value={question} onChange={event => setQuestion(event.target.value)} />
        <label htmlFor="chat-scope">Documents à consulter</label>
        <select id="chat-scope" value={mode} onChange={event => setMode(event.target.value)}>
          <option value="all">Tous mes documents prêts</option><option value="selection">Choisir mes documents</option>
        </select>
        {mode === "selection" && <div className="search-selection">{documents.length ? documents.map(document =>
          <label key={document.id}><input type="checkbox" checked={selection.includes(document.id)} onChange={event =>
            setSelection(old => event.target.checked ? [...old, document.id] : old.filter(id => id !== document.id))} />{document.filename}</label>) : <p>Aucun document prêt.</p>}</div>}
        <label className="external-consent"><input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} />J’accepte l’envoi de ma question, des questions précédentes utiles et des passages à Groq pour cette réponse.</label>
        <p className="field-help">Groq Free reçoit uniquement le contexte borné nécessaire. Pour des documents personnels, activez Zero Data Retention dans les réglages Groq. Sans passage pertinent, l’assistant s’abstient sans appel.</p>
        <button type="submit" disabled={!consent || !question.trim() || (mode === "selection" && !selection.length)}>{busy ? "Traitement en cours…" : "Envoyer ma question"}</button>
      </fieldset>
    </form>
    {error && <p className="form-error" role="alert">{error}</p>}
  </section>;
}
