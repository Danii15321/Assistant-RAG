"use client";

import { useEffect, useRef, useState } from "react";
import { documentRequest, type DocumentRecord, type ExtractedUnit } from "@/lib/documents";

export function ExtractionView({ document, onClose }: { document: DocumentRecord; onClose: () => void }) {
  const section = useRef<HTMLElement>(null);
  useEffect(() => { section.current?.scrollIntoView({ block: "start" }); }, []);
  const [units, setUnits] = useState<ExtractedUnit[]>([]);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    documentRequest(`/documents/${document.id}/extraction?offset=${offset}&limit=20`)
      .then(response => response.json()).then(data => { if (active) { setUnits(data); setError(""); } })
      .catch(failure => { if (active) setError(failure.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [document.id, offset]);
  function navigate(next: number) { setLoading(true); setOffset(next); }
  return <section ref={section} className="extraction-card" aria-labelledby="extraction-title">
    <div className="section-top"><h2 id="extraction-title">Texte extrait · {document.filename}</h2>
      <button type="button" onClick={onClose}>Fermer le texte</button></div>
    <p className="field-help">Repères physiques conservés. Le découpage utilise ce texte exact.</p>
    {loading ? <p role="status">Chargement du texte…</p> : error ? <p role="alert">{error}</p> : units.map(unit =>
      <article className="extracted-unit" key={unit.ordinal}>
        <h3>{{ page: "Page", paragraph: "Paragraphe", line: "Ligne" }[unit.kind] ?? "Repère"} {unit.number}</h3>
        <pre>{unit.text}</pre>
      </article>)}
    <nav className="extraction-pagination" aria-label="Pages de texte extrait">
      <button disabled={loading || offset === 0} onClick={() => navigate(Math.max(0, offset - 20))}>Précédent</button>
      <span>{document.unit_count} repères au total</span>
      <button disabled={loading || offset + 20 >= document.unit_count} onClick={() => navigate(offset + 20)}>Suivant</button>
    </nav>
  </section>;
}
