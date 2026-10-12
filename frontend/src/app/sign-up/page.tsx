import Link from "next/link";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { auth } from "@/lib/auth";
import { AuthForm } from "@/components/auth-form";
export const dynamic = "force-dynamic";
export default async function Page() {
  if (await auth.api.getSession({ headers: await headers() })) redirect("/library");
  return <main className="shell"><header className="header"><Link className="brand" href="/">Assistant RAG</Link></header>
    <section className="auth-panel"><p className="eyebrow">Votre bibliothèque privée</p><h1>Créer mon compte</h1>
      <p>Un nom d’utilisateur et un mot de passe pour retrouver votre espace.</p>
      <AuthForm mode="sign-up" /></section></main>;
}
