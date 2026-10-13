"use client";

import { createPortal } from "react-dom";
import Link from "next/link";
import { useEffect, useId, useRef } from "react";
import { ChatIcon } from "@/components/chat-icon";
import type { AnswerResult } from "@/lib/search";
export type AnswerSource = AnswerResult["sources"][number];
export function sourceLocation(source: AnswerSource) {
  return `${({ page: "Page", paragraph: "Paragraphe", line: "Ligne" } as Record<string, string>)[source.kind] ?? "Repère"} ${source.start_number}${source.end_number !== source.start_number ? ` à ${source.end_number}` : ""}`;
}
export function sourceQuotes(result: AnswerResult, id: string) {
  return Array.from(new Set(result.claims.flatMap(claim => claim.evidence.filter(e => e.source_id === id).map(e => e.quote))));
}
export function SourceDrawer({ result, selected, onClose }: { result: AnswerResult; selected: string; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const title = useId();
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    dialog?.querySelector<HTMLElement>(`[data-selected="true"]`)?.scrollIntoView({ block: "nearest" });
    return () => { dialog?.close(); };
  }, []);
  return createPortal(<dialog ref={ref} className="source-drawer" aria-labelledby={title} onClose={onClose} onClick={event => { if (event.target === event.currentTarget) ref.current?.close(); }}>
    <header className="source-drawer-header"><ChatIcon name="document" /><h2 id={title}>Sources de la réponse</h2><span className="source-count">{result.sources.length}</span><button className="icon-button" aria-label="Fermer les sources" onClick={() => ref.current?.close()} autoFocus><ChatIcon name="close" /></button></header>
    <p className="source-drawer-intro">Les passages qui ont servi à cette réponse. Retrouvez le contexte, vérifiez l’information.</p>
    <div className="source-drawer-content">{result.sources.map(source => <article className="source-detail answer-source" key={source.source_id} data-selected={source.source_id === selected}>
      <div className="source-file"><span className="file-icon"><ChatIcon name="document" /></span><div><h3>{source.filename}</h3><p>{sourceLocation(source)} <span>· {source.source_id}</span></p></div></div>
      {source.status === "deleted" ? <p className="field-help">Source supprimée · Les extraits ont été retirés de l’historique.</p> : <>
        <div className="quoted-evidence"><h4>Extraits cités</h4>{sourceQuotes(result, source.source_id).map(quote => <blockquote key={quote}>{quote}</blockquote>)}</div>
        <details open={source.source_id === selected}><summary>Passage complet</summary><pre>{source.text}</pre></details>
        {source.document_id && <Link className="source-document-link" href={`/library?document=${encodeURIComponent(source.document_id)}`}>Voir le document <ChatIcon name="chevron" /></Link>}
      </>}
    </article>)}</div>
    <p className="source-drawer-footer">Une citation vous permet de vérifier une réponse ; elle ne garantit pas à elle seule son exactitude.</p>
  </dialog>, document.body);
}
