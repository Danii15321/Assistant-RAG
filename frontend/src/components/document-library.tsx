"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ChatIcon } from "@/components/chat-icon";
import { DocumentUpload } from "@/components/document-upload";
import { ExtractionView } from "@/components/extraction-view";
import { PassageView } from "@/components/passage-view";
import { documentRequest, documentStatus, errorMessage, type DocumentRecord } from "@/lib/documents";

export function DocumentLibrary({ initialDocument }: { initialDocument?: string }) {
  const router = useRouter();
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [query, setQuery] = useState("");
  const [format, setFormat] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<DocumentRecord | null>(null);
  const [view, setView] = useState<"text" | "passages">("text");
  const [loadError, setLoadError] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const refresh = useCallback(async () => {
    try {
      const records: DocumentRecord[] = await (await documentRequest("/documents?limit=50")).json();
      setDocuments(records); setLoadError("");
      setSelected(previous => previous && records.some(document => document.id === previous.id) ? previous : null);
    } catch (failure) { setLoadError(failure instanceof Error ? failure.message : "Chargement impossible."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => {
    let active = true;
    documentRequest("/documents?limit=50").then(response => response.json()).then(records => {
      if (active) { setDocuments(records); setLoading(false); if (initialDocument) setSelected(records.find((record: DocumentRecord) => record.id === initialDocument) ?? null); }
    }).catch(failure => { if (active) { setLoadError(failure.message); setLoading(false); } });
    return () => { active = false; };
  }, [initialDocument]);
  useEffect(() => {
    const expired = () => { router.replace("/sign-in"); router.refresh(); };
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, [router]);
  const processing = documents.some(document => document.state === "uploading" || document.state === "queued" || document.state === "processing");
  useEffect(() => {
    if (!processing) return;
    const timer = setInterval(() => { void refresh(); }, 2000);
    return () => clearInterval(timer);
  }, [processing, refresh]);

  async function action(document: DocumentRecord, operation: "delete" | "retry") {
    if (pending) return;
    setPending(document.id); setError("");
    try {
      await documentRequest(`/documents/${document.id}${operation === "retry" ? "/retry" : ""}`,
        operation === "retry" ? "POST" : "DELETE", operation === "retry" ? {} : undefined);
      if (selected?.id === document.id) setSelected(null);
      await refresh();
    } catch (failure) { setError(failure instanceof Error ? failure.message : "L’opération a échoué."); }
    finally { setPending(null); }
  }

  const visible = documents.filter(document => (format === "all" || document.extension === format) && document.filename.toLocaleLowerCase("fr-FR").includes(query.toLocaleLowerCase("fr-FR")));
  return <>
    <div className="library-tools"><details className="library-import"><summary><ChatIcon name="plus" />Ajouter des documents</summary><DocumentUpload onUploaded={refresh} /></details><button className="library-refresh" type="button" onClick={() => void refresh()}>Actualiser</button></div>
    <section className="document-list" aria-labelledby="documents-title">
      <h2 id="documents-title" className="visually-hidden">Mes documents <span className="document-count">{documents.length}</span></h2>
      {(error || loadError) && <p role="alert" className="form-error">{error || loadError}</p>}
      <div className="library-search"><ChatIcon name="search" /><input type="search" aria-label="Rechercher un document" placeholder="Rechercher un document…" value={query} onChange={event => setQuery(event.target.value)} /></div>
      <div className="format-filters" role="group" aria-label="Filtrer par format">{["all", "pdf", "docx", "txt"].map(value => <button key={value} type="button" aria-pressed={format === value} onClick={() => setFormat(value)}>{value === "all" ? "Tous" : value.toUpperCase()} ({documents.filter(d => value === "all" || d.extension === value).length})</button>)}</div>
      {loading ? <p role="status">Chargement de la bibliothèque…</p> : !documents.length ?
        <div className="empty-library"><h3>Votre bibliothèque attend ses premiers documents</h3>
          <p>Importez un document pour consulter son texte extrait.</p></div> :
        !visible.length ? <p className="empty-filter" role="status">Aucun document ne correspond à ces filtres.</p> : <><div className="document-columns" aria-hidden="true"><span>Nom du document</span><span>Format et taille</span><span>Actions</span></div><ul className="document-items">{visible.map(document => <li key={document.id} data-document-id={document.id}>
          <div className="document-information"><span className={`file-icon file-${document.extension}`}><ChatIcon name="document" /></span><div><h3>{document.filename}</h3>

            <p className={`document-status state-${document.state}`}>{documentStatus(document)}</p>
            {document.state === "processing" && document.unit_count > 0 && <p className="field-help">{document.unit_count} repères · {document.embedded_count}/{document.chunk_count} passages indexés</p>}
            {document.error_code && <p className="form-error">{errorMessage(document.error_code)}</p>}</div></div>
          <p className="document-meta"><span className={`format-badge file-${document.extension}`}>{document.extension.toUpperCase()}</span><span>{(document.size_bytes / 1024).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} Kio</span></p><div className="document-actions">
            {document.unit_count > 0 && <button type="button" onClick={() => { setView("text"); setSelected(document); }}>Voir le texte</button>}
            {document.state === "ready" && <button type="button" onClick={() => { setView("passages"); setSelected(document); }}>Voir les passages</button>}
            {document.state === "failed" && <button type="button" disabled={pending !== null} onClick={() => void action(document, "retry")}>Relancer</button>}
            <button className="delete-button" type="button" disabled={pending !== null} onClick={() => void action(document, "delete")}>
              {pending === document.id ? "Traitement…" : "Supprimer"}</button>
          </div></li>)}</ul></>}
      <details className="quiet-details"><summary>Limites et suppression</summary><p>50 documents, 100 Mio et 10 000 passages par compte. Les doublons ne sont conservés qu’une fois. Supprimer un document retire ses extraits des sources ; pour effacer aussi les réponses enregistrées, supprimez les conversations concernées.</p></details>
    </section>
    {selected && (view === "text" ? <ExtractionView key={selected.id} document={selected} onClose={() => setSelected(null)} /> : <PassageView key={selected.id} document={selected} onClose={() => setSelected(null)} />)}
  </>;
}
