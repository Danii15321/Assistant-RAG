import { BrandLogo } from "@/components/brand-logo";
import Link from "next/link";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { auth } from "@/lib/auth";
import { AuthForm } from "@/components/auth-form";
export const dynamic = "force-dynamic";
export default async function Page() {
  if (await auth.api.getSession({ headers: await headers() })) redirect("/conversations");
  return <main className="shell"><header className="header"><Link className="brand" href="/"><BrandLogo />My Talking RAG</Link></header>
    <section className="auth-panel"><h1>Créer mon compte</h1>

      <AuthForm mode="sign-up" /></section></main>;
}
