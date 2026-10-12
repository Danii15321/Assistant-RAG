"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { DocumentUpload } from "@/components/document-upload";
import { ExtractionView } from "@/components/extraction-view";
import { PassageView } from "@/components/passage-view";
import { documentRequest, documentStatus, errorMessage, type DocumentRecord } from "@/lib/documents";

export function DocumentLibrary() {
  const router = useRouter();
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
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
      if (active) { setDocuments(records); setLoading(false); }
    }).catch(failure => { if (active) { setLoadError(failure.message); setLoading(false); } });
    return () => { active = false; };
  }, []);
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

  return <>
    <DocumentUpload onUploaded={refresh} />
    <section className="document-list" aria-labelledby="documents-title">
      <div className="section-top"><h2 id="documents-title">Mes documents <span className="document-count">{documents.length}</span></h2>
        <button type="button" onClick={() => void refresh()}>Actualiser</button></div>
      {(error || loadError) && <p role="alert" className="form-error">{error || loadError}</p>}
      {loading ? <p role="status">Chargement de la bibliothèque…</p> : !documents.length ?
        <div className="empty-library"><h3>Votre bibliothèque attend ses premiers documents</h3>
          <p>Importez un document pour consulter son texte extrait.</p></div> :
        <ul className="document-items">{documents.map(document => <li key={document.id} data-document-id={document.id}>
          <div className="document-information"><h3>{document.filename}</h3>
            <p className="document-meta">{document.extension.toUpperCase()} · {(document.size_bytes / 1024).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} Kio</p>
            <p className={`document-status state-${document.state}`}>{documentStatus(document)}</p>
            {document.unit_count > 0 && <p className="field-help">{document.unit_count} repères · {document.embedded_count}/{document.chunk_count} passages indexés</p>}
            {document.error_code && <p className="form-error">{errorMessage(document.error_code)}</p>}</div>
          <div className="document-actions">
            {document.unit_count > 0 && <button type="button" onClick={() => { setView("text"); setSelected(document); }}>Voir le texte</button>}
            {document.state === "ready" && <button type="button" onClick={() => { setView("passages"); setSelected(document); }}>Voir les passages</button>}
            {document.state === "failed" && <button type="button" disabled={pending !== null} onClick={() => void action(document, "retry")}>Relancer</button>}
            <button className="delete-button" type="button" disabled={pending !== null} onClick={() => void action(document, "delete")}>
              {pending === document.id ? "Traitement…" : "Supprimer"}</button>
          </div></li>)}</ul>}
      <p className="field-help">50 documents, 100 Mio et 10 000 passages par compte. Les doublons ne sont conservés qu’une fois.</p>
    </section>
    {selected && (view === "text" ? <ExtractionView key={selected.id} document={selected} onClose={() => setSelected(null)} /> : <PassageView key={selected.id} document={selected} onClose={() => setSelected(null)} />)}
  </>;
}
