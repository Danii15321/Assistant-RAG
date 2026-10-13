"use client";

import { BrandLogo } from "@/components/brand-logo";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { ChatIcon } from "@/components/chat-icon";
import { SignOutButton } from "@/components/sign-out-button";
import { conversationRequest, type Conversation } from "@/lib/conversations";

function subscribeMobile(callback: () => void) {
  const media = window.matchMedia("(max-width: 700px)");
  media.addEventListener("change", callback);
  return () => media.removeEventListener("change", callback);
}
const isMobile = () => window.matchMedia("(max-width: 700px)").matches;

export function ChatShell({ children, username }: { children: ReactNode; username: string }) {
  const path = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const sidebar = useRef<HTMLElement>(null);
  const toggle = useRef<HTMLButtonElement>(null);
  const mobile = useSyncExternalStore(subscribeMobile, isMobile, () => false);
  useEffect(() => {
    if (!open) return;
    toggle.current?.focus();
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape") { setOpen(false); toggle.current?.focus(); }
    }
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [open]);
  const [items, setItems] = useState<Conversation[]>([]);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    function load() {
      conversationRequest<Conversation[]>("?limit=50", controller.signal)
        .then(data => { if (!controller.signal.aborted) { setItems(data); setError(""); } })
        .catch(failure => { if (!controller.signal.aborted) setError(failure.message); });
    }
    function expire() { controller.abort(); setItems([]); window.location.replace("/sign-in?expired=1"); }
    load();
    window.addEventListener("conversations-changed", load);
    window.addEventListener("session-expired", expire);
    return () => { controller.abort(); window.removeEventListener("conversations-changed", load); window.removeEventListener("session-expired", expire); };
  }, [path]);
  async function remove(id: string) {
    if (busy) return;
    setBusy(true); setError("");
    try {
      await conversationRequest<void>(`/${id}`, new AbortController().signal, "DELETE");
      setItems(previous => previous.filter(item => item.id !== id)); setDeleting(null);
      if (path === `/conversations/${id}`) { router.push("/conversations"); setOpen(false); }
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Suppression impossible."); }
    finally { setBusy(false); }
  }
  function newChat() {
    setOpen(false);
    if (path === "/conversations") window.dispatchEvent(new Event("new-conversation"));
    else router.push("/conversations");
  }
  return <div className={`chat-shell${open ? " menu-open" : ""}`}>
    <a className="skip-link" href="#workspace">Aller au contenu</a>
    {open && <button className="sidebar-backdrop" aria-label="Fermer le panneau latéral" onClick={() => setOpen(false)} />}
    <aside ref={sidebar} className="chat-sidebar" id="chat-sidebar" aria-label="Navigation principale" onKeyDown={event => {
      if (open && mobile && event.key === "Tab") {
        const controls = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('a[href], button:not(:disabled)'));
        const target = event.shiftKey ? controls.at(-1) : controls[0];
        if (document.activeElement === (event.shiftKey ? controls[0] : controls.at(-1))) { event.preventDefault(); target?.focus(); }
      }
    }}>
      <button ref={toggle} id="sidebar-toggle" className="sidebar-logo rail-action" aria-label={open ? "Masquer le panneau latéral" : "Ouvrir le panneau latéral"} data-tooltip={open ? "Masquer le panneau latéral" : "Ouvrir le panneau latéral"} aria-expanded={open} aria-controls="sidebar-details" onClick={() => setOpen(!open)}><BrandLogo /><span className="rail-label">My Talking <strong>RAG</strong></span></button>
      <button className="new-chat-button rail-action" aria-label="Nouvelle discussion" data-tooltip="Nouvelle discussion" onClick={newChat}><ChatIcon name="compose" /><span className="rail-label">Nouvelle discussion</span></button>
      <nav className="workspace-links" aria-label="Votre espace">
        <Link href="/library" className="rail-action" aria-label="Documents" data-tooltip="Documents" aria-current={path === "/library" ? "page" : undefined} onClick={() => setOpen(false)}><ChatIcon name="document" /><span className="rail-label">Documents</span></Link>
        <Link href="/settings" className="rail-action" aria-label="Paramètres" data-tooltip="Paramètres" aria-current={path === "/settings" ? "page" : undefined} onClick={() => setOpen(false)}><ChatIcon name="settings" /><span className="rail-label">Paramètres</span></Link>
      </nav>
      <div className="sidebar-history" id="sidebar-details" hidden={!open}>
        <h2>Mes conversations</h2>
        {!items.length && !error && <p className="sidebar-empty">Vos échanges apparaîtront ici.</p>}
        <ul>{items.map(item => <li key={item.id} className={path === `/conversations/${item.id}` ? "active" : ""}>
          <Link href={`/conversations/${item.id}`} aria-current={path === `/conversations/${item.id}` ? "page" : undefined} onClick={() => setOpen(false)} title={item.title}>{item.title}</Link>
          <button className="history-delete" aria-label={`Supprimer la conversation ${item.title}`} onClick={() => setDeleting(item.id)}><ChatIcon name="trash" /></button>
          {deleting === item.id && <div className="delete-confirmation"><p>Effacer cette conversation et ses messages ?</p><button disabled={busy} onClick={() => void remove(item.id)}>Confirmer la suppression</button><button disabled={busy} onClick={() => setDeleting(null)}>Annuler</button></div>}
        </li>)}</ul>
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
      <Link className="advanced-search rail-action" aria-label="Explorer les passages" data-tooltip="Explorer les passages" href="/search" onClick={() => setOpen(false)}><ChatIcon name="search" /><span className="rail-label">Explorer les passages</span></Link>
      {!open ? <button className="rail-account rail-action" aria-label="Ouvrir mon compte et l’historique" data-tooltip="Compte et historique" onClick={() => setOpen(true)}><span className="account-avatar" aria-hidden="true">{username.charAt(0).toUpperCase()}</span></button> : <div className="sidebar-account"><span className="account-avatar" aria-hidden="true">{username.charAt(0).toUpperCase()}</span><span className="account-name"><span>{username}</span><small>Espace privé</small></span><SignOutButton /></div>}
    </aside>
    <div className="workspace-main" inert={(open && mobile) || undefined}>

      <main id="workspace" tabIndex={-1}>{children}</main>
    </div>
  </div>;
}
