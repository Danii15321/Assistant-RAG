import { headers } from "next/headers";
import { redirect } from "next/navigation";
import Link from "next/link";
import { auth } from "@/lib/auth";
import { SearchPanel } from "@/components/search-panel";
import { SignOutButton } from "@/components/sign-out-button";

export const dynamic = "force-dynamic";
export default async function SearchPage() {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) redirect("/sign-in");
  return <main className="shell">
    <header className="header"><Link className="brand" href="/">Assistant RAG</Link><SignOutButton /></header>
    <nav className="private-navigation" aria-label="Espace privé"><Link href="/conversations">Mes conversations</Link></nav>
    <section className="library-heading"><p className="eyebrow">Espace privé</p><h1>Recherche documentaire</h1>
      <p><Link href="/library">Retour à ma bibliothèque</Link></p></section>
    <SearchPanel />
    <footer>Projet personnel · Démonstration CV · Budget de 0 €</footer>
  </main>;
}
