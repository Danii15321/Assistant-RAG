"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { AnswerResults } from "@/components/answer-results";
import { ConversationForm } from "@/components/conversation-form";
import { conversationRequest, newRequestId, type Conversation, type Exchange, type MessageInput } from "@/lib/conversations";
import { documentRequest, errorMessage, type DocumentRecord } from "@/lib/documents";

export function ConversationPanel({ id }: { id?: string }) {
  const router = useRouter();
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [items, setItems] = useState<Exchange[]>([]);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [outgoing, setOutgoing] = useState("");
  const [error, setError] = useState("");
  const [uncertain, setUncertain] = useState<MessageInput | null>(null);
  const [formReset, setFormReset] = useState<{ version: number; selection: string[] | null }>({ version: 0, selection: null });
  const controller = useRef<AbortController | null>(null);
  const activeId = useRef(id);
  const mutation = useRef(false);
  const bottom = useRef<HTMLDivElement>(null);
  const refresh = useCallback(async (signal: AbortSignal) => {
    if (!activeId.current) return [];
    const entries = await conversationRequest<Exchange[]>(`/${activeId.current}/messages?limit=100`, signal);
    if (!signal.aborted) setItems(entries);
    return entries;
  }, []);
  const refreshDocuments = useCallback(async () => {
    const records: DocumentRecord[] = await (await documentRequest("/documents")).json();
    if (!controller.current?.signal.aborted) setDocuments(records);
  }, []);
  useEffect(() => {
    const request = new AbortController(); controller.current = request;
    const detail = id ? conversationRequest<Conversation>(`/${id}`, request.signal) : Promise.resolve(null);
    const entries = id ? conversationRequest<Exchange[]>(`/${id}/messages?limit=100`, request.signal) : Promise.resolve([]);
    Promise.all([detail, entries, refreshDocuments()])
      .then(([record, exchanges]) => { if (!request.signal.aborted) { setConversation(record); setItems(exchanges); } })
      .catch(failure => { if (!request.signal.aborted) setError(failure.message); })
      .finally(() => { if (!request.signal.aborted) setLoading(false); });
    function expire() { request.abort(); setItems([]); setDocuments([]); setConversation(null); window.location.replace("/sign-in?expired=1"); }
    function reset() {
      if (mutation.current || activeId.current) return;
      setFormReset(old => ({ version: old.version + 1, selection: null })); setError("");
    }
    window.addEventListener("session-expired", expire);
    window.addEventListener("new-conversation", reset);
    return () => { request.abort(); window.removeEventListener("session-expired", expire); window.removeEventListener("new-conversation", reset); };
  }, [id, refreshDocuments]);
  const processing = documents.some(document => ["uploading", "queued", "processing"].includes(document.state));
  useEffect(() => {
    if (!processing) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try { await refreshDocuments(); }
      catch (failure) { if (!stopped) setError(failure instanceof Error ? failure.message : "Actualisation impossible."); }
      if (!stopped) timer = setTimeout(() => void poll(), 2000);
    }
    timer = setTimeout(() => void poll(), 2000);
    return () => { stopped = true; clearTimeout(timer); };
  }, [processing, refreshDocuments]);
  const pending = items.some(item => item.state === "pending");
  useEffect(() => {
    if (!pending) return;
    const request = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const entries = await refresh(request.signal);
        if (!request.signal.aborted && entries.some(item => item.state === "pending")) timer = setTimeout(() => void poll(), 1000);
      } catch (failure) { if (!request.signal.aborted) setError(failure instanceof Error ? failure.message : "Actualisation impossible."); }
    }
    timer = setTimeout(() => void poll(), 1000);
    return () => { request.abort(); clearTimeout(timer); };
  }, [pending, refresh]);
  useEffect(() => { if (items.length || sending) bottom.current?.scrollIntoView({ block: "end" }); }, [items.length, sending]);
  async function send(body: MessageInput): Promise<boolean> {
    if (mutation.current || !controller.current) return false;
    mutation.current = true; setSending(true); setOutgoing(body.question); setError("");
    const signal = controller.current.signal;
    try {
      if (!activeId.current) {
        const created = await conversationRequest<Conversation>("", signal, "POST");
        activeId.current = created.id; setConversation(created);
        window.dispatchEvent(new Event("conversations-changed"));
      }
      const item = await conversationRequest<Exchange>(`/${activeId.current}/messages`, signal, "POST", body);
      if (signal.aborted) return false;
      setUncertain(null);
      setItems(old => [...old.filter(entry => entry.id !== item.id), item].sort((a, b) => a.ordinal - b.ordinal));
      const detail = await conversationRequest<Conversation>(`/${activeId.current}`, signal);
      if (!signal.aborted) {
        setConversation(detail); window.dispatchEvent(new Event("conversations-changed"));
        if (!id) router.replace(`/conversations/${activeId.current}`);
      }
      return true;
    } catch (failure) {
      if (signal.aborted) return false;
      setError(failure instanceof Error ? failure.message : "L’envoi a échoué.");
      if (!activeId.current) return false;
      try {
        const entries = await refresh(signal);
        const saved = entries.find(item => item.request_id === body.request_id);
        setUncertain(saved ? null : body);
        if (saved && !id) router.replace(`/conversations/${activeId.current}`);
        return Boolean(saved);
      } catch { if (!signal.aborted) setUncertain(body); }
      return false;
    } finally { mutation.current = false; if (!signal.aborted) { setSending(false); setOutgoing(""); } }
  }
  async function recover() {
    if (!uncertain) return;
    const body = uncertain;
    if (await send(body)) setFormReset(old => ({ version: old.version + 1, selection: body.document_ids }));
  }
  const empty = !items.length && !sending;
  return <section className={`chat-panel${empty ? " is-empty" : ""}`} aria-label="Conversation privée">
    {loading ? <p className="chat-loading" role="status">Chargement de votre espace…</p> : id && !conversation ? <div className="chat-error"><p role="alert">{error || "Cette conversation n’est plus disponible."}</p><Link href="/conversations">Nouvelle conversation</Link></div> : <>
      {empty ? <div className="chat-welcome"><h1>Par où commence-t-on ?</h1></div> :
        <h1 className="conversation-heading">{conversation?.title ?? "Nouvelle conversation"}</h1>}
      <div className="conversation-history" aria-label="Historique de la conversation">
        {items.map(item => <article className="chat-exchange" key={item.id} aria-labelledby={`question-${item.id}`}>
          <div className="chat-question"><span className="visually-hidden">Vous</span><h2 id={`question-${item.id}`}>{item.question}</h2><time className="message-time" dateTime={item.created_at}>{new Date(item.created_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}</time></div>
          {item.answer && <AnswerResults result={item.answer} prefix={`answer-${item.id}`} />}
          {item.state === "pending" && <p className="chat-thinking" role="status">Recherche dans vos documents…</p>}
          {item.state === "failed" && <p className="form-error" role="status">Échange échoué : {errorMessage(item.error_code)} La question est conservée.</p>}
        </article>)}
        {sending && <div className="outgoing-message"><div className="chat-question"><h2>{outgoing}</h2></div><p className="chat-thinking" role="status">Recherche et rédaction en cours… Le premier chargement peut prendre une minute.</p></div>}
        <div ref={bottom} />
      </div>
      {error && <p role="alert" className="form-error chat-error">{error}</p>}
      {uncertain && <div className="recovery-note"><p>L’envoi n’est pas encore confirmé. Vérifiez son état pour éviter un doublon.</p><button disabled={sending} onClick={() => void recover()}>Vérifier l’envoi</button></div>}
      <ConversationForm key={formReset.version} initialSelection={formReset.version ? formReset.selection : items.at(-1)?.document_ids ?? null} documents={documents} onUploaded={refreshDocuments}
        busy={sending || pending || Boolean(uncertain)} onSend={(question, selection) => send({ request_id: newRequestId(), question, document_ids: selection, allow_external_processing: true })} />
    </>}
  </section>;
}
