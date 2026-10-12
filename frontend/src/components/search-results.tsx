import { type SearchResult } from "@/lib/search";

export function SearchResults({ result }: { result: SearchResult }) {
  return <section className="extraction-card" aria-labelledby="search-results-title">
    <h2 id="search-results-title">Résultats de la recherche</h2>
    <p role="status">{result.status === "empty_corpus" ? "Aucun document prêt dans votre bibliothèque." :
      result.status === "no_match" ? "Aucun passage suffisamment proche de votre question." :
      `${result.hits.length} passage${result.hits.length > 1 ? "s" : ""} retrouvé${result.hits.length > 1 ? "s" : ""}.`}</p>
    <p className="field-help">Le score mesure la proximité des textes ; il ne garantit pas que le passage répond à la question.
      Seuil : {result.threshold.toFixed(3)}. Aucune réponse n’est générée à cette étape.</p>
    {result.hits.map(hit => <article className="extracted-unit search-hit" key={`${hit.document_id}:${hit.generation}:${hit.ordinal}`}>
      <h3>{hit.filename} · {{ page: "Page", paragraph: "Paragraphe", line: "Ligne" }[hit.kind] ?? "Repère"} {hit.start_number}{hit.end_number !== hit.start_number ? ` à ${hit.end_number}` : ""}</h3>
      <p className="field-help">Passage {hit.ordinal} · Score {hit.score.toFixed(3)}</p>
      <details><summary>Lire le passage</summary><pre>{hit.text}</pre></details>
    </article>)}
  </section>;
}
