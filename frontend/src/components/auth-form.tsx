"use client";

import { useState, useSyncExternalStore, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

const subscribe = () => () => {};
export function AuthForm({ mode }: { mode: "sign-in" | "sign-up" }) {
  const router = useRouter();
  const ready = useSyncExternalStore(subscribe, () => true, () => false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const register = mode === "sign-up";
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const data = new FormData(event.currentTarget);
    const password = String(data.get("password"));
    if (register && password !== data.get("confirmation")) { setError("Les mots de passe ne correspondent pas."); return; }
    setPending(true);
    try {
      const response = await fetch(`/api/auth/${mode}/username`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ username: data.get("username"), password }),
      });
      if (!response.ok) {
        const result: unknown = await response.json();
        setError(result && typeof result === "object" && "message" in result && typeof result.message === "string"
          ? result.message : "Connexion indisponible.");
        return;
      }
      router.replace("/library");
      router.refresh();
    } catch { setError("Connexion indisponible. Vérifiez votre connexion et réessayez."); }
    finally { setPending(false); }
  }
  return <form className="auth-form" onSubmit={submit}>
    <label htmlFor="username">Nom d’utilisateur</label>
    <input id="username" name="username" required autoComplete="username" maxLength={64}
      autoCapitalize="none" spellCheck={false} placeholder="prenom.nom" aria-describedby="username-help" />
    <p className="field-help" id="username-help">Format prenom.nom, sans accents. Les chiffres et les traits d’union sont acceptés.</p>
    <label htmlFor="password">Mot de passe</label>
    <input id="password" name="password" type="password" required minLength={register ? 12 : undefined}
      maxLength={128} autoComplete={register ? "new-password" : "current-password"} aria-describedby={register ? "password-help" : undefined} />
    {register && <><p className="field-help" id="password-help">12 caractères minimum. Une phrase longue est facile à retenir.</p>
      <label htmlFor="confirmation">Confirmer le mot de passe</label>
      <input id="confirmation" name="confirmation" type="password" required maxLength={128} autoComplete="new-password" /></>}
    {error && <p className="form-error" role="alert">{error}</p>}
    <button disabled={!ready || pending} type="submit">{pending ? "Veuillez patienter…" : register ? "Créer mon compte" : "Se connecter"}</button>
    <p className="auth-switch">{register ? "Déjà un compte ? " : "Première visite ? "}
      <Link href={register ? "/sign-in" : "/sign-up"}>{register ? "Se connecter" : "Créer mon compte"}</Link></p>
  </form>;
}
