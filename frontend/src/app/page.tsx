import Link from "next/link";
import { ConnectionStatus } from "@/components/connection-status";

const steps = [
  { number: "01", title: "Vos documents", detail: "Rassemblez vos PDF, fichiers Word et notes dans une bibliothèque privée." },
  { number: "02", title: "Vos questions", detail: "Retrouvez les passages utiles à partir d’une question, dans vos propres mots." },
  { number: "03", title: "Vos sources", detail: "Vérifiez chaque réponse avec les extraits et les repères du document d’origine." },
];

export default function Home() {
  return (
    <main className="shell">
      <header className="header">
        <Link className="brand" href="/" aria-label="Assistant RAG, accueil">
          <span className="brand-icon" aria-hidden="true">a</span>
          Assistant RAG
        </Link>
        <span className="badge">Démonstration personnelle</span>
      </header>

      <section className="hero" aria-labelledby="hero-title">
        <p className="eyebrow">Votre bibliothèque. Des réponses vérifiables.</p>
        <h1 id="hero-title">Faites parler<br />vos <span>documents.</span></h1>
        <p className="intro">Un assistant pour retrouver l’essentiel dans vos cours, vos supports et vos notes — avec les sources pour vérifier.</p>
        <p className="progress-note">Importez vos documents, recherchez les passages proches de votre question et vérifiez les sources dans votre espace privé. Générez une réponse sourcée avec Groq Free, ouvrez les extraits cités et reprenez vos conversations enregistrées.</p>
      <Link className="primary-link" href="/sign-in">Accéder à mon espace <span aria-hidden="true">↗</span></Link>
      </section>

      <section className="steps" aria-label="Le parcours prévu dans la première version">
        {steps.map((step) => (
          <article className="step" key={step.number}>
            <span className="step-number" aria-hidden="true">{step.number}</span>
            <h2>{step.title}</h2>
            <p>{step.detail}</p>
          </article>
        ))}
      </section>

      <ConnectionStatus />
      <footer>Projet personnel · Démonstration CV · Budget de 0 €</footer>
    </main>
  );
}
