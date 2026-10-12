"use client";

import { useEffect, useState } from "react";
import { documentRequest, type DocumentRecord, type IndexedPassage } from "@/lib/documents";

export function PassageView({ document, onClose }: { document: DocumentRecord; onClose: () => void }) {
  const [passages, setPassages] = useState<IndexedPassage[]>([]);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    documentRequest(`/documents/${document.id}/passages?offset=${offset}&limit=10`)
      .then(response => response.json()).then(data => { if (active) { setPassages(data); setError(""); } })
      .catch(failure => { if (active) setError(failure.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [document.id, offset]);
  function navigate(next: number) { setLoading(true); setOffset(next); }
  return <section className="extraction-card" aria-labelledby="passages-title">
    <div className="section-top"><h2 id="passages-title">Passages indexés · {document.filename}</h2>
      <button type="button" onClick={onClose}>Fermer les passages</button></div>
    <p className="field-help">Texte exact et repères conservés. Les questions seront disponibles à une prochaine étape.</p>
    {loading ? <p role="status">Chargement des passages…</p> : error ? <p role="alert">{error}</p> : passages.map(passage =>
      <article className="extracted-unit indexed-passage" key={passage.ordinal}>
        <h3>Passage {passage.ordinal} · {{ page: "Page", paragraph: "Paragraphe", line: "Ligne" }[passage.kind] ?? "Repère"} {passage.start_number}{passage.end_number !== passage.start_number ? ` à ${passage.end_number}` : ""}</h3>
        <p className="field-help">{passage.token_count} tokens</p>
        <pre>{passage.text}</pre>
      </article>)}
    <nav className="extraction-pagination" aria-label="Pages de passages indexés">
      <button disabled={loading || offset === 0} onClick={() => navigate(Math.max(0, offset - 10))}>Précédent</button>
      <span>{document.chunk_count} passages au total</span>
      <button disabled={loading || offset + 10 >= document.chunk_count} onClick={() => navigate(offset + 10)}>Suivant</button>
    </nav>
  </section>;
}
