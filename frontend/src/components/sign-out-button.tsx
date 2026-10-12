"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

export function SignOutButton() {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);
  async function signOut() {
    setPending(true); setError(false);
    try {
      const result = await fetch("/api/auth/sign-out", { method: "POST", headers: { "content-type": "application/json" }, body: "{}" });
      if (!result.ok) { setError(true); return; }
      router.replace("/sign-in"); router.refresh();
    } catch { setError(true); }
    finally { setPending(false); }
  }
  return <div><button type="button" onClick={signOut} disabled={pending}>{pending ? "Déconnexion…" : "Se déconnecter"}</button>
    {error && <p className="form-error" role="alert">Déconnexion impossible. Réessayez.</p>}</div>;
}
