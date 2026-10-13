import { BrandLogo } from "@/components/brand-logo";
import Link from "next/link";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { auth } from "@/lib/auth";
import { ConnectionStatus } from "@/components/connection-status";

export default async function Home() {
  if (await auth.api.getSession({ headers: await headers() })) redirect("/conversations");
  return (
    <main className="shell">
      <header className="header">
        <Link className="brand" href="/" aria-label="My Talking RAG, accueil">
          <BrandLogo />
          My Talking RAG
        </Link>
      </header>

      <section className="hero" aria-labelledby="hero-title">
        <h1 id="hero-title">Faites parler<br />vos <span>documents.</span></h1>
        <p className="intro">Un assistant pour retrouver l’essentiel dans vos cours, vos supports et vos notes — avec les sources pour vérifier.</p>
      <Link className="primary-link" href="/sign-in">Accéder à mon espace <span aria-hidden="true">↗</span></Link>
      </section>

      <details className="quiet-details service-details"><summary>État du service</summary><ConnectionStatus /></details>
    </main>
  );
}
