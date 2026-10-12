"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { AnswerResults } from "@/components/answer-results";
import { ConversationForm } from "@/components/conversation-form";
import { conversationRequest, newRequestId, type Conversation, type Exchange, type MessageInput } from "@/lib/conversations";
import { documentRequest, errorMessage, type DocumentRecord } from "@/lib/documents";

export function ConversationPanel({ id }: { id: string }) {
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [items, setItems] = useState<Exchange[]>([]);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [uncertain, setUncertain] = useState<MessageInput | null>(null);
  const [formReset, setFormReset] = useState<{ version: number; selection: string[] | null }>({ version: 0, selection: null });
  const controller = useRef<AbortController | null>(null);
  const mutation = useRef(false);
  const refresh = useCallback(async (signal: AbortSignal) => {
    const entries = await conversationRequest<Exchange[]>(`/${id}/messages?limit=100`, signal);
    if (!signal.aborted) setItems(entries);
    return entries;
  }, [id]);
  useEffect(() => {
    const request = new AbortController(); controller.current = request;
    Promise.all([conversationRequest<Conversation>(`/${id}`, request.signal), conversationRequest<Exchange[]>(`/${id}/messages?limit=100`, request.signal), documentRequest("/documents").then(response => response.json())])
      .then(([detail, entries, ready]: [Conversation, Exchange[], DocumentRecord[]]) => {
        if (!request.signal.aborted) { setConversation(detail); setItems(entries); setDocuments(ready.filter(document => document.state === "ready")); }
      }).catch(failure => { if (!request.signal.aborted) setError(failure.message); })
      .finally(() => { if (!request.signal.aborted) setLoading(false); });
    function expire() { request.abort(); setItems([]); setConversation(null); setDocuments([]); window.location.replace("/sign-in?expired=1"); }
    window.addEventListener("session-expired", expire);
    return () => { request.abort(); window.removeEventListener("session-expired", expire); };
  }, [id, refresh]);
  const pending = items.some(item => item.state === "pending");
  useEffect(() => {
    if (!pending) return;
    const request = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try { const entries = await refresh(request.signal);
        if (!request.signal.aborted && entries.some(item => item.state === "pending")) timer = setTimeout(() => void poll(), 1000);
      } catch (failure) { if (!request.signal.aborted) setError(failure instanceof Error ? failure.message : "Actualisation impossible."); }
    }
    timer = setTimeout(() => void poll(), 1000);
    return () => { request.abort(); clearTimeout(timer); };
  }, [pending, refresh]);
  async function send(body: MessageInput): Promise<boolean> {
    if (mutation.current) return false;
    mutation.current = true; setSending(true); setError("");
    const signal = controller.current!.signal;
    try {
      const item = await conversationRequest<Exchange>(`/${id}/messages`, signal, "POST", body);
      if (signal.aborted) return false;
      setUncertain(null);
      setItems(old => [...old.filter(entry => entry.id !== item.id), item].sort((a, b) => a.ordinal - b.ordinal));
      const detail = await conversationRequest<Conversation>(`/${id}`, signal);
      if (!signal.aborted) setConversation(detail);
      return true;
    } catch (failure) {
      if (signal.aborted) return false;
      setError(failure instanceof Error ? failure.message : "L’envoi a échoué.");
      try {
        const entries = await refresh(signal);
        const saved = entries.find(item => item.request_id === body.request_id);
        setUncertain(saved ? null : body);
        return Boolean(saved);
      } catch { if (!signal.aborted) setUncertain(body); }
      return false;
    } finally { mutation.current = false; if (!signal.aborted) setSending(false); }
  }
  async function recover() {
    if (!uncertain) return;
    const body = uncertain;
    if (await send(body)) setFormReset(old => ({ version: old.version + 1, selection: body.document_ids }));
  }
  return <section aria-labelledby="chat-title">
    <h1 id="chat-title" className="chat-title">{conversation?.title ?? "Conversation privée"}</h1>
    <p className="field-help">Les échanges restent dans votre compte. Supprimer un document retire les extraits de ses citations ; les textes des réponses restent dans l’historique. Supprimez aussi la conversation pour les effacer.</p>
    {loading ? <p role="status">Chargement de la conversation…</p> : conversation && <>
      <div className="conversation-history" aria-label="Historique de la conversation">
        {!items.length && <p>Votre première question ouvrira cet échange.</p>}
        {items.map(item => <article className="chat-exchange" key={item.id} aria-labelledby={`question-${item.id}`}>
          <div className="chat-question"><p className="eyebrow">Vous · Échange {item.ordinal}</p><h2 id={`question-${item.id}`}>{item.question}</h2>
            <p className="field-help">{new Date(item.created_at).toLocaleString("fr-FR")} · {item.document_ids === null ? "Tous les documents prêts au moment de la recherche" : `${item.document_ids.length} document(s) sélectionné(s)`}</p></div>
          {item.answer && <AnswerResults result={item.answer} prefix={`answer-${item.id}`} />}
          {item.state === "pending" && <p role="status">Recherche et réponse en cours… L’échange est enregistré ; vous pouvez recharger cette page.</p>}
          {item.state === "failed" && <p className="form-error" role="status">Échange échoué : {errorMessage(item.error_code)} La question est conservée. Vous pouvez la renvoyer après résolution du problème.</p>}
        </article>)}
      </div>
      {sending && <p role="status">Traitement en cours. Le premier chargement du modèle peut prendre une minute.</p>}
      {uncertain && <div className="document-list"><p>Le résultat de cet envoi n’est pas encore connu. Vérifiez-le avec le même identifiant pour éviter un doublon.</p>
        <button disabled={sending} onClick={() => void recover()}>Vérifier l’envoi</button></div>}
      <ConversationForm key={formReset.version} initialSelection={formReset.selection} documents={documents} busy={sending || pending || Boolean(uncertain)} onSend={(question, selection) => send({ request_id: newRequestId(), question, document_ids: selection, allow_external_processing: true })} />
      <p><Link href="/library">Importer ou gérer mes documents</Link></p>
    </>}
    {error && <p role="alert" className="form-error">{error}</p>}
  </section>;
}
