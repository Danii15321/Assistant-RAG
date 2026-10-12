"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { documentRequest, type DocumentRecord } from "@/lib/documents";
import { generateAnswer, searchDocuments, type AnswerResult, type SearchResult } from "@/lib/search";
import { AnswerResults } from "@/components/answer-results";
import { SearchResults } from "@/components/search-results";

export function SearchPanel() {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState("all");
  const [selection, setSelection] = useState<string[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [answer, setAnswer] = useState<AnswerResult | null>(null);
  const [consent, setConsent] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => {
    let active = true;
    documentRequest("/documents").then(response => response.json()).then((items: DocumentRecord[]) => {
      if (active) setDocuments(items.filter(document => document.state === "ready"));
    }).catch(failure => { if (active) setError(failure.message); })
      .finally(() => { if (active) setLoading(false); });
    function expire() { controller.current?.abort(); setResult(null); setAnswer(null); window.location.replace("/sign-in?expired=1"); }
    window.addEventListener("session-expired", expire);
    return () => { active = false; controller.current?.abort(); window.removeEventListener("session-expired", expire); };
  }, []);
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); void run(false); }
  async function run(generation: boolean) {
    if (pending) return;
    setResult(null); setAnswer(null); setError("");
    if (mode === "selection" && !selection.length) { setError("Choisissez au moins un document."); return; }
    const request = new AbortController();
    controller.current = request; setPending(true);
    try {
      if (generation) {
        const response = await generateAnswer(question, mode === "all" ? null : selection, request.signal);
        if (!request.signal.aborted) setAnswer(response);
      } else {
        const response = await searchDocuments(question, mode === "all" ? null : selection, request.signal);
        if (!request.signal.aborted) setResult(response);
      }
    } catch (failure) { if (!request.signal.aborted) setError(failure instanceof Error ? failure.message : "La recherche a échoué."); }
    finally { if (!request.signal.aborted) setPending(false); }
  }
  return <>
    <section className="document-list" aria-labelledby="search-form-title">
      <h2 id="search-form-title">Rechercher dans mes documents</h2>
      <p>Retrouvez les passages proches de votre question, puis vérifiez leur contenu.</p>
      <p className="field-help">La recherche des passages reste locale. La génération envoie votre question et les passages retenus à Groq Free.</p>
      {loading ? <p role="status">Chargement des documents…</p> : <form className="search-form" onSubmit={submit}>
        <fieldset disabled={pending || !documents.length}>
          <label htmlFor="search-question">Votre question</label>
          <textarea id="search-question" required maxLength={1000} rows={3} value={question}
            onChange={event => { setQuestion(event.target.value); setResult(null); setAnswer(null); }} />
          <label htmlFor="search-scope">Documents à consulter</label>
          <select id="search-scope" value={mode} onChange={event => { setMode(event.target.value); setResult(null); setAnswer(null); }}>
            <option value="all">Tous mes documents prêts</option><option value="selection">Choisir mes documents</option>
          </select>
          {mode === "selection" && <div className="search-selection">{documents.map(document =>
            <label key={document.id}><input type="checkbox" checked={selection.includes(document.id)}
              onChange={event => { setSelection(old => event.target.checked ? [...old, document.id] : old.filter(id => id !== document.id)); setResult(null); setAnswer(null); }} />{document.filename}</label>)}</div>}
          <button type="submit" disabled={!question.trim()}>{pending ? "Recherche en cours…" : "Rechercher les passages"}</button>
          <label className="external-consent"><input type="checkbox" checked={consent}
            onChange={event => setConsent(event.target.checked)} />J’accepte l’envoi de ma question et des passages à Groq pour cette réponse.</label>
          <p className="field-help">Pour des documents personnels, activez Zero Data Retention dans les réglages Groq. Cette page permet un essai ponctuel ; utilisez « Mes conversations » pour enregistrer vos échanges.</p>
          <button type="button" disabled={!consent || !question.trim()} onClick={() => void run(true)}>Générer une réponse sourcée</button>
        </fieldset>
      </form>}
      {!loading && !documents.length && <p>Aucun document prêt. Importez un document dans votre bibliothèque pour commencer.</p>}
      {pending && <p role="status">Traitement en cours. Le premier chargement du modèle peut prendre une minute.</p>}
      {error && <p role="alert" className="form-error">{error}</p>}
    </section>
    {result && <SearchResults result={result} />}
    {answer && <AnswerResults result={answer} />}
  </>;
}
