"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { conversationRequest, type Conversation } from "@/lib/conversations";

export function ConversationList() {
  const [items, setItems] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  const mutation = useRef(false);
  const router = useRouter();
  useEffect(() => {
    const request = new AbortController(); controller.current = request;
    conversationRequest<Conversation[]>("?limit=50", request.signal).then(data => {
      if (!request.signal.aborted) setItems(data);
    }).catch(failure => { if (!request.signal.aborted) setError(failure.message); })
      .finally(() => { if (!request.signal.aborted) setLoading(false); });
    function expire() { request.abort(); setItems([]); window.location.replace("/sign-in?expired=1"); }
    window.addEventListener("session-expired", expire);
    return () => { request.abort(); window.removeEventListener("session-expired", expire); };
  }, []);
  async function create() {
    if (mutation.current) return;
    mutation.current = true; setBusy(true); setError("");
    try {
      const item = await conversationRequest<Conversation>("", controller.current!.signal, "POST");
      router.push(`/conversations/${item.id}`);
    } catch (failure) { if (!controller.current?.signal.aborted) setError(failure instanceof Error ? failure.message : "Création impossible."); }
    finally { mutation.current = false; if (!controller.current?.signal.aborted) setBusy(false); }
  }
  async function remove(id: string) {
    if (mutation.current) return;
    mutation.current = true; setBusy(true); setError("");
    try {
      await conversationRequest<void>(`/${id}`, controller.current!.signal, "DELETE");
      setItems(old => old.filter(item => item.id !== id)); setDeleting(null);
    } catch (failure) { if (!controller.current?.signal.aborted) setError(failure instanceof Error ? failure.message : "Suppression impossible."); }
    finally { mutation.current = false; if (!controller.current?.signal.aborted) setBusy(false); }
  }
  return <section className="document-list" aria-labelledby="conversation-list-title">
    <div className="section-top"><h2 id="conversation-list-title">Mes conversations</h2>
      <button disabled={busy || loading} onClick={() => void create()}>Nouvelle conversation</button></div>
    <p className="field-help">Questions, réponses et sources sont enregistrées dans votre compte. Jusqu’à 50 conversations et 100 échanges par conversation.</p>
    {loading ? <p role="status">Chargement de l’historique…</p> : items.length === 0 ? <p>Aucune conversation. Commencez un échange depuis vos documents.</p> :
      <ul className="document-items conversation-items">{items.map(item => <li key={item.id}>
        <div className="document-information"><h3><Link href={`/conversations/${item.id}`}>{item.title}</Link></h3>
          <p className="document-meta">Mis à jour le {new Date(item.updated_at).toLocaleString("fr-FR")}</p></div>
        {deleting === item.id ? <div className="delete-confirmation"><p>Effacer définitivement cette conversation, ses messages et ses citations ?</p>
          <button disabled={busy} onClick={() => void remove(item.id)}>Confirmer la suppression</button>{" "}
          <button disabled={busy} onClick={() => setDeleting(null)}>Annuler</button></div> :
          <button disabled={busy} aria-label={`Supprimer la conversation ${item.title}`} onClick={() => setDeleting(item.id)}>Supprimer</button>}
      </li>)}</ul>}
    {error && <p role="alert" className="form-error">{error}</p>}
  </section>;
}
