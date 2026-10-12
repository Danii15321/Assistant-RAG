import { headers } from "next/headers";
import { redirect } from "next/navigation";
import Link from "next/link";
import { auth } from "@/lib/auth";
import { SignOutButton } from "@/components/sign-out-button";
import { ConversationList } from "@/components/conversation-list";

export const dynamic = "force-dynamic";
export default async function ConversationsPage() {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) redirect("/sign-in");
  return <main className="shell">
    <header className="header"><Link className="brand" href="/">Assistant RAG</Link><SignOutButton /></header>
    <nav className="private-navigation" aria-label="Espace privé"><Link href="/library">Ma bibliothèque</Link><Link href="/conversations">Mes conversations</Link><Link href="/search">Recherche de passages</Link></nav>
    <ConversationList />
    <footer>Projet personnel · Démonstration CV · Budget de 0 €</footer>
  </main>;
}
