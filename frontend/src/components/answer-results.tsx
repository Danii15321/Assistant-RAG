"use client";

import { useState } from "react";
import { modelLabels } from "@/lib/models";
import { BrandLogo } from "@/components/brand-logo";
import { ChatIcon } from "@/components/chat-icon";
import { SourceDrawer, sourceLocation, sourceQuotes } from "@/components/source-drawer";
import { type AnswerResult } from "@/lib/search";

export function AnswerResults({ result, prefix = "answer" }: { result: AnswerResult; prefix?: string }) {
  const [selected, setSelected] = useState<string | null>(null);
  return <section className="extraction-card answer-card" aria-labelledby={`${prefix}-title`}>
    <div className="answer-author"><BrandLogo /><h2 id={`${prefix}-title`}>My Talking RAG <span>{result.provider_called ? modelLabels[result.model ?? "groq"] : "Documents consultés"}</span></h2></div>
    {result.state === "insufficient_context" ? <p role="status">{result.answer}</p> :
      <div className="answer-claims">{result.claims.map((claim, index) => <p key={index}>
        {claim.text} {Array.from(new Set(claim.evidence.map(item => item.source_id))).map(reference =>
          <a key={reference} href={`#${prefix}-${reference}`} onClick={event => { event.preventDefault(); setSelected(reference); }} aria-haspopup="dialog">[{reference}]</a>)}
      </p>)}</div>}
    {result.sources.length > 0 && <div className="answer-sources"><h3><ChatIcon name="document" />Sources <span className="source-count">{result.sources.length}</span></h3>
      <div className="source-card-grid">{result.sources.map(source => <article id={`${prefix}-${source.source_id}`} key={source.source_id} className="source-preview">
        {source.status === "deleted" ? <div className="source-deleted"><p>{source.filename} · {sourceLocation(source)}</p><p className="field-help">Source supprimée · Les extraits ont été retirés de l’historique.</p></div> :
          <button className="source-card" aria-label={`Vérifier la source ${source.source_id}`} aria-haspopup="dialog" onClick={() => setSelected(source.source_id)}>
            <span className="source-file"><span className="file-icon"><ChatIcon name="document" /></span><span><strong>{source.filename}</strong><small>{sourceLocation(source)} · {source.source_id}</small></span><ChatIcon name="chevron" /></span>
            <span className="source-preview-quote">« {sourceQuotes(result, source.source_id)[0] ?? source.text} »</span>
          </button>}
      </article>)}</div></div>}
    {selected && <SourceDrawer result={result} selected={selected} onClose={() => setSelected(null)} />}
  </section>;
}
