import { type AnswerResult } from "@/lib/search";

export function AnswerResults({ result, prefix = "answer" }: { result: AnswerResult; prefix?: string }) {
  return <section className="extraction-card" aria-labelledby={`${prefix}-title`}>
    <h2 id={`${prefix}-title`}>Réponse sourcée</h2>
    {result.state === "insufficient_context" ? <p role="status">{result.answer}</p> :
      <div className="answer-claims">{result.claims.map((claim, index) => <p key={index}>
        {claim.text} {Array.from(new Set(claim.evidence.map(item => item.source_id))).map(reference =>
          <a key={reference} href={`#${prefix}-${reference}`}>[{reference}] </a>)}
      </p>)}</div>}
    {result.sources.map(source => <article className="extracted-unit answer-source" id={`${prefix}-${source.source_id}`} key={source.source_id}>
      <h3>[{source.source_id}] {source.filename} · {{ page: "Page", paragraph: "Paragraphe", line: "Ligne" }[source.kind] ?? "Repère"} {source.start_number}{source.end_number !== source.start_number ? ` à ${source.end_number}` : ""}</h3>
      {source.status === "deleted" ? <p className="field-help">Source supprimée · Les extraits ont été retirés de l’historique.</p> : <details><summary>Vérifier la source {source.source_id}</summary>
        <p className="field-help">Extraits cités :</p>
        {Array.from(new Set(result.claims.flatMap(claim => claim.evidence.filter(evidence => evidence.source_id === source.source_id).map(evidence => evidence.quote))))
          .map(quote => <blockquote key={quote}>{quote}</blockquote>)}
        <p className="field-help">Passage documentaire :</p><pre>{source.text}</pre>
      </details>}
    </article>)}
    <p className="field-help">Vérifiez les extraits : une référence valide ne garantit pas à elle seule l’exactitude de la réponse.</p>
  </section>;
}
